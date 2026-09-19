# SPDX-License-Identifier: LGPL-2.1-or-later

"""UI-neutral document model for the BIM Navigator."""

from dataclasses import dataclass

from .model import BIMViewManagerModel
from .scope import BIMViewScope


@dataclass(frozen=True)
class ProjectNode:
    """A project-context object and its navigable children."""

    object: object
    kind: str
    children: tuple = ()


@dataclass(frozen=True)
class NavigatorSection:
    """One virtual root in the BIM Navigator."""

    key: str
    label: str
    items: tuple


@dataclass(frozen=True)
class SheetNode:
    """A BIM sheet and the saved-view placements it contains."""

    page: object
    placements: tuple


@dataclass(frozen=True)
class SheetPlacementNode:
    """One TechDraw placement and its linked saved BIM view."""

    drawing_view: object
    definition: object


class BIMNavigatorModel:
    """Expose Project, Views, Current View, Sheets, and Issues without Qt."""

    def __init__(self, document, legacy_view_predicate=None, type_resolver=None):
        self.document = document
        self.views = BIMViewManagerModel(document, legacy_view_predicate)
        self._type_resolver = type_resolver or _draft_type

    # Compatibility surface used by the existing Views Manager during the
    # incremental migration to the navigator UI.
    def saved_views(self):
        return self.views.saved_views()

    def saved_view_groups(self):
        return self.views.saved_view_groups()

    def pages(self):
        return self.views.pages()

    def sheet_nodes(self):
        from bimsheets import BIMSheetService

        sheet_service = BIMSheetService(self.document)
        result = []
        for page in self.pages():
            if not sheet_service.is_sheet(page):
                continue
            placements = tuple(
                SheetPlacementNode(view, view.BIMViewDefinition)
                for view in getattr(page, "Views", ())
                if getattr(view, "BIMViewDefinition", None) is not None
            )
            result.append(SheetNode(page, placements))
        return tuple(
            sorted(
                result,
                key=lambda node: (
                    getattr(node.page, "SheetOrder", 0),
                    getattr(node.page, "SheetNumber", ""),
                    node.page.Label.casefold(),
                ),
            )
        )

    def issues(self):
        from bimsheets import BIMSheetIssueService

        return BIMSheetIssueService(self.document).issues()

    def legacy_views(self):
        return self.views.legacy_views()

    def project_nodes(self):
        objects = tuple(getattr(self.document, "Objects", ()))
        buildings = tuple(obj for obj in objects if self._kind(obj) == "Building")
        storeys = tuple(obj for obj in objects if self._kind(obj) == "Storey")
        proxies = tuple(obj for obj in objects if self._kind(obj) == "WorkingPlane")
        section_planes = tuple(obj for obj in objects if self._kind(obj) == "SectionPlane")

        owned_storeys = set()
        owned_proxies = set()
        owned_section_planes = set()
        roots = []
        for building in buildings:
            children = []
            for storey in self._group(building):
                if self._kind(storey) != "Storey":
                    continue
                owned_storeys.add(storey)
                node = self._storey_node(
                    storey, owned_proxies, owned_section_planes
                )
                children.append(node)
            children.sort(key=lambda node: self._elevation(node.object))
            roots.append(ProjectNode(building, "Building", tuple(children)))

        unowned_storeys = []
        for storey in storeys:
            if storey in owned_storeys:
                continue
            unowned_storeys.append(
                self._storey_node(storey, owned_proxies, owned_section_planes)
            )
        unowned_storeys.sort(key=lambda node: self._elevation(node.object))
        roots.extend(unowned_storeys)
        roots.extend(
            ProjectNode(proxy, "WorkingPlane")
            for proxy in proxies
            if proxy not in owned_proxies
        )
        roots.extend(
            ProjectNode(plane, "SectionPlane")
            for plane in section_planes
            if plane not in owned_section_planes
        )
        return tuple(roots)

    def current_view_scope(self, definition=None):
        definition = definition or self._active_view()
        source = getattr(definition, "BIMContextSource", None) if definition else None
        if source is not None:
            objects = self._descendants(source)
        else:
            objects = tuple(
                obj
                for obj in getattr(self.document, "Objects", ())
                if not self.views.is_saved_view(obj)
                and not obj.isDerivedFrom("TechDraw::DrawPage")
            )
        return BIMViewScope.from_objects(objects, definition=definition, source=source)

    def sections(self, definition=None):
        return (
            NavigatorSection("Project", "Project", self.project_nodes()),
            NavigatorSection("Views", "Views", self.saved_view_groups()),
            NavigatorSection(
                "CurrentView", "Current View", (self.current_view_scope(definition),)
            ),
            NavigatorSection("Sheets", "Sheets", self.sheet_nodes()),
            NavigatorSection("Issues", "Issues", self.issues()),
        )

    def _storey_node(self, storey, owned_proxies, owned_section_planes):
        proxies = tuple(
            obj for obj in self._group(storey) if self._kind(obj) == "WorkingPlane"
        )
        section_planes = tuple(
            obj for obj in self._group(storey) if self._kind(obj) == "SectionPlane"
        )
        owned_proxies.update(proxies)
        owned_section_planes.update(section_planes)
        return ProjectNode(
            storey,
            "Storey",
            tuple(ProjectNode(proxy, "WorkingPlane") for proxy in proxies)
            + tuple(ProjectNode(plane, "SectionPlane") for plane in section_planes),
        )

    def _active_view(self):
        for view in self.saved_views():
            if bool(getattr(view, "BIMIsActiveView", False)):
                return view
        return None

    def _descendants(self, root):
        result = []
        seen = {root}
        pending = list(self._group(root))
        while pending:
            obj = pending.pop(0)
            if obj in seen:
                continue
            seen.add(obj)
            result.append(obj)
            pending.extend(self._group(obj))
        return tuple(result)

    def _kind(self, obj):
        draft_type = self._type_resolver(obj)
        if draft_type in {"Building", "IfcBuilding"} or getattr(obj, "IfcType", "") == "Building":
            return "Building"
        if draft_type in {
            "BuildingPart",
            "Building Storey",
            "IfcBuildingStorey",
        } or getattr(obj, "IfcType", "") == "Building Storey":
            return "Storey"
        if draft_type == "WorkingPlaneProxy":
            return "WorkingPlane"
        if getattr(getattr(obj, "Proxy", None), "Type", "") == "SectionPlane":
            return (
                "ElevationMarker"
                if str(getattr(obj, "Purpose", "")) == "Elevation"
                else "SectionPlane"
            )
        return "Object"

    @staticmethod
    def _group(obj):
        group = tuple(getattr(obj, "Group", ()) or ())
        if group:
            return group
        if getattr(getattr(obj, "Proxy", None), "Type", "") == "SectionPlane":
            return tuple(getattr(obj, "Objects", ()) or ())
        return ()

    @staticmethod
    def _elevation(obj):
        elevation = getattr(obj, "Elevation", None)
        if elevation is not None:
            return float(getattr(elevation, "Value", elevation))
        try:
            return float(obj.Placement.Base.z)
        except (AttributeError, TypeError):
            return 0.0


def _draft_type(obj):
    try:
        import Draft

        return Draft.getType(obj)
    except (AttributeError, ImportError, RuntimeError):
        return ""
