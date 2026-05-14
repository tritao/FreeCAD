// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileNotice: Part of the FreeCAD project.
/******************************************************************************
 *                                                                            *
 *   © 2026 FreeCAD contributors                                              *
 *                                                                            *
 *   FreeCAD is free software: you can redistribute it and/or modify          *
 *   it under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1            *
 *   of the License, or (at your option) any later version.                   *
 *                                                                            *
 *   FreeCAD is distributed in the hope that it will be useful,               *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty              *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                  *
 *   See the GNU Lesser General Public License for more details.              *
 *                                                                            *
 *   You should have received a copy of the GNU Lesser General Public         *
 *   License along with FreeCAD. If not, see https://www.gnu.org/licenses     *
 *                                                                            *
 ******************************************************************************/

#include "PreCompiled.h"

#include <algorithm>
#include <set>

#include <QColor>
#include <QColorDialog>
#include <QEvent>
#include <QListWidgetItem>
#include <QSignalBlocker>
#include <QTimer>

#include <Base/Placement.h>
#include <Base/Rotation.h>
#include <Base/Tools.h>
#include <Base/Vector3D.h>
#include <TopAbs_ShapeEnum.hxx>
#include <TopExp_Explorer.hxx>

#include <App/ClippingPlane.h>
#include <App/Document.h>
#include <App/DocumentObject.h>
#include <App/GeoFeature.h>
#include <Gui/ClippingPlaneHelperFit.h>
#include <Gui/ClippingPlaneManager.h>
#include <Gui/Document.h>
#include <Gui/Inventor/Draggers/Gizmo.h>
#include <Gui/PlaneGizmoEditor.h>
#include <Gui/QuantitySpinBox.h>
#include <Gui/Selection/Selection.h>
#include <Gui/View3DInventor.h>
#include <Gui/View3DInventorViewer.h>
#include <Gui/ViewProviderClippingPlane.h>

#include <Mod/Part/App/FeatureSectionAnalysis.h>

#include "TaskSectionAnalysis.h"
#include "ViewProviderSectionAnalysis.h"
#include "ui_TaskSectionAnalysis.h"

using namespace PartGui;

namespace
{

int countSubShapes(const Part::TopoShape& shape, TopAbs_ShapeEnum type)
{
    if (shape.isNull()) {
        return 0;
    }

    int count = 0;
    for (TopExp_Explorer explorer(shape.getShape(), type); explorer.More(); explorer.Next()) {
        ++count;
    }
    return count;
}

Gui::ViewProviderClippingPlane* getClippingPlaneViewProvider(
    PartGui::ViewProviderSectionAnalysis* viewProvider,
    App::ClippingPlane* plane
)
{
    auto* guiDocument = viewProvider ? viewProvider->getDocument() : nullptr;
    if (!guiDocument || !plane) {
        return nullptr;
    }

    return freecad_cast<Gui::ViewProviderClippingPlane*>(guiDocument->getViewProvider(plane));
}

}  // namespace

class SectionAnalysisWidget::Private
{
public:
    Ui::SectionAnalysisWidget ui {};
    ViewProviderSectionAnalysis* viewProvider {nullptr};
    QTimer* recomputeTimer {nullptr};
};

/* TRANSLATOR PartGui::SectionAnalysisWidget */

SectionAnalysisWidget::SectionAnalysisWidget(ViewProviderSectionAnalysis* viewProvider, QWidget* parent)
    : QWidget(parent)
    , d(std::make_unique<Private>())
{
    d->viewProvider = viewProvider;
    d->ui.setupUi(this);

    d->ui.planeOffsetSpin->setUnit(Base::Unit::Length);
    d->ui.planeOffsetSpin->setRange(-1.0e9, 1.0e9);
    d->ui.planeOffsetSpin->setSingleStep(1.0);

    d->ui.planeTiltXSpin->setUnit(Base::Unit::Angle);
    d->ui.planeTiltXSpin->setRange(-89.99, 89.99);
    d->ui.planeTiltXSpin->setSingleStep(1.0);

    d->ui.planeTiltYSpin->setUnit(Base::Unit::Angle);
    d->ui.planeTiltYSpin->setRange(-180.0, 180.0);
    d->ui.planeTiltYSpin->setSingleStep(1.0);

    d->recomputeTimer = new QTimer(this);
    d->recomputeTimer->setSingleShot(true);
    d->recomputeTimer->setInterval(150);
    connect(d->recomputeTimer, &QTimer::timeout, this, &SectionAnalysisWidget::flushQueuedSectionRecompute);

    setupConnections();
    refresh();
}

SectionAnalysisWidget::~SectionAnalysisWidget()
{
    stopPlaneEditing();
}

ViewProviderSectionAnalysis* SectionAnalysisWidget::getViewProvider() const
{
    return d->viewProvider;
}

Part::SectionAnalysis* SectionAnalysisWidget::getSectionAnalysis() const
{
    auto* vp = getViewProvider();
    return vp ? vp->getObject<Part::SectionAnalysis>() : nullptr;
}

App::ClippingPlane* SectionAnalysisWidget::getClippingPlane() const
{
    auto* analysis = getSectionAnalysis();
    return analysis ? freecad_cast<App::ClippingPlane*>(analysis->ClippingPlane.getValue()) : nullptr;
}

Gui::View3DInventor* SectionAnalysisWidget::getCurrentView() const
{
    auto* vp = getViewProvider();
    auto* doc = vp ? vp->getDocument() : nullptr;
    return doc ? qobject_cast<Gui::View3DInventor*>(doc->getActiveView()) : nullptr;
}

Base::Placement SectionAnalysisWidget::currentEditablePlanePlacement() const
{
    if (planeEditor) {
        return planeEditor->currentPlacement();
    }

    if (auto* plane = getClippingPlane()) {
        return App::GeoFeature::getGlobalPlacement(plane);
    }

    return {};
}

void SectionAnalysisWidget::refresh()
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    {
        const QSignalBlocker resultModeBlocker(d->ui.resultModeCombo);
        d->ui.resultModeCombo->setCurrentIndex(static_cast<int>(analysis->ResultMode.getValue()));
    }

    refreshClippingPlane();
    refreshSources();
    refreshPlane();
    refreshResult();
    refreshActivation();
    refreshAppearance();
    refreshButtons();
}

void SectionAnalysisWidget::refreshClippingPlane()
{
    auto* plane = getClippingPlane();
    if (!plane) {
        d->ui.clippingPlaneValue->setText(tr("Not linked"));
        d->ui.clippingPlaneValue->setToolTip(QString());
        return;
    }

    d->ui.clippingPlaneValue->setText(QString::fromUtf8(plane->Label.getValue()));
    d->ui.clippingPlaneValue->setToolTip(QString::fromUtf8(plane->getNameInDocument()));
}

void SectionAnalysisWidget::refreshSources()
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    d->ui.sourcesList->clear();
    for (auto* source : analysis->Sources.getValues()) {
        if (!source) {
            continue;
        }

        auto* item
            = new QListWidgetItem(QString::fromUtf8(source->Label.getValue()), d->ui.sourcesList);
        item->setData(Qt::UserRole, QByteArray(source->getNameInDocument()));
        item->setToolTip(QString::fromUtf8(source->getNameInDocument()));
    }

    d->ui.sourcesSummaryLabel->setText(
        tr("%1 source object(s)").arg(analysis->Sources.getValues().size())
    );
}

void SectionAnalysisWidget::refreshPlane()
{
    auto* plane = getClippingPlane();

    const QSignalBlocker flipBlocker(d->ui.flipClippingDirectionCheck);
    const QSignalBlocker offsetBlocker(d->ui.planeOffsetSpin);
    const QSignalBlocker tiltXBlocker(d->ui.planeTiltXSpin);
    const QSignalBlocker tiltYBlocker(d->ui.planeTiltYSpin);
    const QSignalBlocker helperSizeModeBlocker(d->ui.helperSizeModeCombo);

    if (!plane) {
        d->ui.flipClippingDirectionCheck->setChecked(false);
        d->ui.planeOffsetSpin->setValue(0.0);
        d->ui.planeTiltXSpin->setValue(0.0);
        d->ui.planeTiltYSpin->setValue(0.0);
        d->ui.helperSizeModeCombo->setCurrentIndex(
            static_cast<int>(Gui::ViewProviderClippingPlane::HelperSizeModeOption::Screen)
        );
        return;
    }

    d->ui.flipClippingDirectionCheck->setChecked(plane->Reverse.getValue());
    const auto state = Gui::PlaneGizmoEditor::stateFromPlacement(currentEditablePlanePlacement());
    d->ui.planeOffsetSpin->setValue(Base::Quantity(state.offset, Base::Unit::Length));
    d->ui.planeTiltXSpin->setValue(Base::Quantity(state.tiltXDegrees, Base::Unit::Angle));
    d->ui.planeTiltYSpin->setValue(Base::Quantity(state.tiltYDegrees, Base::Unit::Angle));
    if (auto* clippingPlaneViewProvider = getClippingPlaneViewProvider(getViewProvider(), plane)) {
        d->ui.helperSizeModeCombo->setCurrentIndex(
            static_cast<int>(clippingPlaneViewProvider->HelperSizeMode.getValue())
        );
    }
}

void SectionAnalysisWidget::refreshResult()
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    const int edgeCount = countSubShapes(analysis->Shape.getShape(), TopAbs_EDGE);
    const int faceCount = countSubShapes(analysis->Shape.getShape(), TopAbs_FACE);
    d->ui.resultSummaryLabel->setText(tr("%1 edge(s), %2 face(s)").arg(edgeCount).arg(faceCount));
}

void SectionAnalysisWidget::refreshActivation()
{
    auto* plane = getClippingPlane();
    auto* view = getCurrentView();
    const QSignalBlocker blocker(d->ui.activeInCurrentViewCheck);

    if (!plane || !view) {
        d->ui.activeInCurrentViewCheck->setChecked(false);
        d->ui.activationStateLabel->setVisible(true);
        d->ui.activationStateLabel->setText(
            plane ? tr("No active 3D view is available.")
                  : tr("Link a clipping plane to preview this analysis in a 3D view.")
        );
        return;
    }

    const bool active = Gui::ClippingPlaneManager::instance().isActive(view, plane);
    d->ui.activeInCurrentViewCheck->setChecked(active);
    d->ui.activationStateLabel->clear();
    d->ui.activationStateLabel->setVisible(false);
}

void SectionAnalysisWidget::refreshAppearance()
{
    auto* viewProvider = getViewProvider();
    if (!viewProvider) {
        return;
    }

    setColorButtonPreview(d->ui.sectionFaceColorButton, viewProvider->SectionFaceColor.getValue());
    setColorButtonPreview(d->ui.sectionEdgeColorButton, viewProvider->SectionEdgeColor.getValue());
    setColorButtonPreview(d->ui.hatchColorButton, viewProvider->HatchColor.getValue());

    const QSignalBlocker transparencyBlocker(d->ui.sectionFaceTransparencySpin);
    d->ui.sectionFaceTransparencySpin->setValue(viewProvider->SectionFaceTransparency.getValue());

    const QSignalBlocker hatchEdgeColorBlocker(d->ui.useSectionEdgeColorForHatchingCheck);
    d->ui.useSectionEdgeColorForHatchingCheck->setChecked(
        viewProvider->UseSectionEdgeColorForHatching.getValue()
    );

    const QSignalBlocker hatchLineWidthBlocker(d->ui.hatchLineWidthSpin);
    d->ui.hatchLineWidthSpin->setValue(viewProvider->HatchLineWidth.getValue());

    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    const QSignalBlocker showHatchingBlocker(d->ui.showHatchingCheck);
    d->ui.showHatchingCheck->setChecked(analysis->ShowHatching.getValue());

    const QSignalBlocker hatchSpacingBlocker(d->ui.hatchSpacingSpin);
    d->ui.hatchSpacingSpin->setValue(analysis->HatchSpacing.getValue());

    const QSignalBlocker hatchAngleBlocker(d->ui.hatchAngleSpin);
    d->ui.hatchAngleSpin->setValue(analysis->HatchAngle.getValue());
}

void SectionAnalysisWidget::refreshButtons()
{
    auto* analysis = getSectionAnalysis();
    const bool hasDocument = analysis && analysis->getDocument();
    const bool hasPlane = getClippingPlane() != nullptr;
    const bool editingPlaneIn3D = planeEditor && planeEditor->isActive();
    const bool hasSources = analysis && !analysis->Sources.getValues().empty();
    const bool hasView = getCurrentView() != nullptr;
    const bool presetNeedsView = d->ui.planePresetCombo->currentIndex()
        == static_cast<int>(Gui::PlaneGizmoEditor::Preset::View);
    const bool hatchEnabled = analysis && analysis->ShowHatching.getValue();
    auto* viewProvider = getViewProvider();
    const bool useEdgeColorForHatching = viewProvider
        && viewProvider->UseSectionEdgeColorForHatching.getValue();

    d->ui.useCurrentSelectionAsClippingPlaneButton->setEnabled(hasDocument);
    d->ui.selectClippingPlaneButton->setEnabled(hasPlane);
    {
        const QSignalBlocker blocker(d->ui.editClippingPlaneButton);
        d->ui.editClippingPlaneButton->setChecked(editingPlaneIn3D);
    }
    d->ui.editClippingPlaneButton->setEnabled(hasPlane && hasView);
    d->ui.flipClippingDirectionCheck->setEnabled(hasPlane);
    d->ui.planeOffsetSpin->setEnabled(hasPlane);
    d->ui.planeTiltXSpin->setEnabled(hasPlane);
    d->ui.planeTiltYSpin->setEnabled(hasPlane);
    d->ui.planePresetCombo->setEnabled(hasPlane);
    d->ui.applyPlanePresetButton->setEnabled(hasPlane && (!presetNeedsView || hasView));
    d->ui.helperSizeModeCombo->setEnabled(hasPlane);
    d->ui.fitHelperToSourcesButton->setEnabled(hasPlane && hasSources);
    d->ui.fitHelperToSelectionButton->setEnabled(hasPlane && hasDocument);
    d->ui.useCurrentSelectionButton->setEnabled(hasDocument);
    d->ui.appendCurrentSelectionButton->setEnabled(hasDocument);
    d->ui.removeSelectedSourcesButton->setEnabled(!d->ui.sourcesList->selectedItems().isEmpty());
    d->ui.selectSourcesButton->setEnabled(hasSources);
    d->ui.recomputeButton->setEnabled(hasPlane && hasSources && !editingPlaneIn3D);
    d->ui.activeInCurrentViewCheck->setEnabled(hasPlane && hasView);
    d->ui.showHatchingCheck->setEnabled(hasSources);
    d->ui.hatchSpacingSpin->setEnabled(hasSources && hatchEnabled);
    d->ui.hatchAngleSpin->setEnabled(hasSources && hatchEnabled);
    d->ui.useSectionEdgeColorForHatchingCheck->setEnabled(hasSources && hatchEnabled);
    d->ui.hatchColorButton->setEnabled(hasSources && hatchEnabled && !useEdgeColorForHatching);
    d->ui.hatchLineWidthSpin->setEnabled(hasSources && hatchEnabled);

    d->ui.useSectionEdgeColorForHatchingCheck->setVisible(hatchEnabled);
    d->ui.hatchColorLabel->setVisible(hatchEnabled);
    d->ui.hatchColorButton->setVisible(hatchEnabled);
    d->ui.hatchLineWidthLabel->setVisible(hatchEnabled);
    d->ui.hatchLineWidthSpin->setVisible(hatchEnabled);
    d->ui.hatchSpacingLabel->setVisible(hatchEnabled);
    d->ui.hatchSpacingSpin->setVisible(hatchEnabled);
    d->ui.hatchAngleLabel->setVisible(hatchEnabled);
    d->ui.hatchAngleSpin->setVisible(hatchEnabled);
}

void SectionAnalysisWidget::setClippingPlane(App::ClippingPlane* plane)
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    stopPlaneEditing();
    analysis->ClippingPlane.setValue(plane);
    if (auto* doc = analysis->getDocument()) {
        doc->recompute();
    }
    refresh();
}

void SectionAnalysisWidget::setColorButtonPreview(QPushButton* button, const Base::Color& color)
{
    if (!button) {
        return;
    }

    const QColor qtColor = QColor::fromRgbF(color.r, color.g, color.b, 1.0);
    button->setText(qtColor.name(QColor::HexRgb).toUpper());
    button->setStyleSheet(QString::fromLatin1("background-color: %1;").arg(qtColor.name()));
}

void SectionAnalysisWidget::setSources(const std::vector<App::DocumentObject*>& sources)
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    analysis->Sources.setValues(sources);
    if (auto* doc = analysis->getDocument()) {
        doc->recompute();
    }
    refresh();
}

void SectionAnalysisWidget::recomputeSectionAnalysisIfReady()
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    auto* doc = analysis->getDocument();
    if (!doc) {
        refresh();
        return;
    }

    if (getClippingPlane() && !analysis->Sources.getValues().empty()) {
        doc->recompute();
    }

    refresh();
}

Gui::PlaneGizmoEditor* SectionAnalysisWidget::ensurePlaneEditor()
{
    auto* vp = getViewProvider();
    auto* doc = vp ? vp->getDocument() : nullptr;
    auto* plane = getClippingPlane();
    auto* planeViewProvider = (plane && doc)
        ? freecad_cast<Gui::ViewProviderClippingPlane*>(doc->getViewProvider(plane))
        : nullptr;

    if (!planeViewProvider) {
        planeEditor.reset();
        return nullptr;
    }

    if (planeEditor && planeEditor->getViewProvider() == planeViewProvider) {
        return planeEditor.get();
    }

    planeEditor = std::make_unique<Gui::PlaneGizmoEditor>(planeViewProvider, this);
    connect(planeEditor.get(), &Gui::PlaneGizmoEditor::stateChanged, this, [this]() {
        refreshPlane();
        refreshActivation();
        refreshButtons();
    });
    connect(planeEditor.get(), &Gui::PlaneGizmoEditor::editingChanged, this, [this](bool) {
        refreshButtons();
    });
    connect(planeEditor.get(), &Gui::PlaneGizmoEditor::committed, this, [this]() {
        recomputeSectionAnalysisIfReady();
    });
    return planeEditor.get();
}

bool SectionAnalysisWidget::startDedicatedPlaneGizmoEdit()
{
    auto* view = getCurrentView();
    auto* editor = ensurePlaneEditor();
    if (!editor || !view) {
        return false;
    }
    return editor->start(view->getViewer());
}

void SectionAnalysisWidget::finishDedicatedPlaneGizmoEdit(bool commitPreview)
{
    if (planeEditor && planeEditor->isActive()) {
        planeEditor->finish(commitPreview);
    }
}

void SectionAnalysisWidget::queueSectionRecompute()
{
    if (planeEditor && planeEditor->isActive()) {
        return;
    }
    d->recomputeTimer->start();
}

void SectionAnalysisWidget::flushQueuedSectionRecompute()
{
    recomputeSectionAnalysisIfReady();
}

void SectionAnalysisWidget::stopPlaneEditing()
{
    if (planeEditor && planeEditor->isActive()) {
        finishDedicatedPlaneGizmoEdit(true);
    }
    else {
        auto* vp = getViewProvider();
        auto* doc = vp ? vp->getDocument() : nullptr;
        auto* plane = getClippingPlane();
        auto* planeViewProvider = (plane && doc)
            ? freecad_cast<Gui::ViewProviderClippingPlane*>(doc->getViewProvider(plane))
            : nullptr;
        if (planeViewProvider) {
            planeViewProvider->finishPanelPlaneEdit();
        }
    }
}

std::vector<App::DocumentObject*> SectionAnalysisWidget::getSelectedSourceObjects() const
{
    std::vector<App::DocumentObject*> sources;
    std::set<std::string> sourceNames;

    auto* analysis = getSectionAnalysis();
    if (!analysis || !analysis->getDocument()) {
        return sources;
    }

    auto* plane = getClippingPlane();
    for (const auto& selected :
         Gui::Selection().getSelection(analysis->getDocument()->getName(), Gui::ResolveMode::NoResolve)) {
        auto* object = selected.pObject;
        if (!object || object == analysis || object == plane
            || object->getDocument() != analysis->getDocument()
            || object->isDerivedFrom(App::ClippingPlane::getClassTypeId())) {
            continue;
        }

        if (sourceNames.insert(object->getNameInDocument()).second) {
            sources.push_back(object);
        }
    }

    return sources;
}

App::ClippingPlane* SectionAnalysisWidget::getSelectedClippingPlane() const
{
    auto* analysis = getSectionAnalysis();
    if (!analysis || !analysis->getDocument()) {
        return nullptr;
    }

    App::ClippingPlane* plane = nullptr;
    for (const auto& selected :
         Gui::Selection().getSelection(analysis->getDocument()->getName(), Gui::ResolveMode::NoResolve)) {
        auto* object = selected.pObject;
        if (!object || object->getDocument() != analysis->getDocument()) {
            continue;
        }

        auto* candidate = freecad_cast<App::ClippingPlane*>(object);
        if (!candidate) {
            continue;
        }

        if (plane && plane != candidate) {
            return nullptr;
        }

        plane = candidate;
    }

    return plane;
}

void SectionAnalysisWidget::selectObjects(const std::vector<App::DocumentObject*>& objects)
{
    auto* analysis = getSectionAnalysis();
    if (!analysis || !analysis->getDocument()) {
        return;
    }

    Gui::Selection().clearSelection(analysis->getDocument()->getName());
    for (auto* object : objects) {
        if (!object) {
            continue;
        }
        Gui::Selection().addSelection(analysis->getDocument()->getName(), object->getNameInDocument());
    }
}

void SectionAnalysisWidget::setupConnections()
{
    connect(
        d->ui.resultModeCombo,
        qOverload<int>(&QComboBox::currentIndexChanged),
        this,
        &SectionAnalysisWidget::onResultModeChanged
    );
    connect(d->ui.recomputeButton, &QPushButton::clicked, this, &SectionAnalysisWidget::onRecomputeClicked);
    connect(
        d->ui.useCurrentSelectionButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onUseCurrentSelectionAsSources
    );
    connect(
        d->ui.appendCurrentSelectionButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onAppendCurrentSelectionAsSources
    );
    connect(
        d->ui.removeSelectedSourcesButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onRemoveSelectedSources
    );
    connect(
        d->ui.sourcesList,
        &QListWidget::itemSelectionChanged,
        this,
        &SectionAnalysisWidget::refreshButtons
    );
    connect(d->ui.selectSourcesButton, &QPushButton::clicked, this, &SectionAnalysisWidget::onSelectSources);
    connect(
        d->ui.activeInCurrentViewCheck,
        &QCheckBox::toggled,
        this,
        &SectionAnalysisWidget::onActivationToggled
    );
    connect(
        d->ui.selectClippingPlaneButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onSelectClippingPlane
    );
    connect(
        d->ui.useCurrentSelectionAsClippingPlaneButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onUseCurrentSelectionAsClippingPlane
    );
    connect(
        d->ui.flipClippingDirectionCheck,
        &QCheckBox::toggled,
        this,
        &SectionAnalysisWidget::onFlipClippingDirectionToggled
    );
    connect(
        d->ui.planeOffsetSpin,
        qOverload<double>(&Gui::QuantitySpinBox::valueChanged),
        this,
        &SectionAnalysisWidget::onPlaneControlsChanged
    );
    connect(
        d->ui.planeTiltXSpin,
        qOverload<double>(&Gui::QuantitySpinBox::valueChanged),
        this,
        &SectionAnalysisWidget::onPlaneControlsChanged
    );
    connect(
        d->ui.planeTiltYSpin,
        qOverload<double>(&Gui::QuantitySpinBox::valueChanged),
        this,
        &SectionAnalysisWidget::onPlaneControlsChanged
    );
    connect(
        d->ui.planePresetCombo,
        qOverload<int>(&QComboBox::currentIndexChanged),
        this,
        &SectionAnalysisWidget::refreshButtons
    );
    connect(
        d->ui.applyPlanePresetButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onApplyPlanePreset
    );
    connect(
        d->ui.helperSizeModeCombo,
        qOverload<int>(&QComboBox::currentIndexChanged),
        this,
        &SectionAnalysisWidget::onHelperSizeModeChanged
    );
    connect(
        d->ui.fitHelperToSourcesButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onFitHelperToSources
    );
    connect(
        d->ui.fitHelperToSelectionButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onFitHelperToSelection
    );
    connect(
        d->ui.editClippingPlaneButton,
        &QPushButton::toggled,
        this,
        &SectionAnalysisWidget::onEditClippingPlaneToggled
    );
    connect(
        d->ui.sectionFaceColorButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onSectionFaceColorClicked
    );
    connect(
        d->ui.sectionEdgeColorButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onSectionEdgeColorClicked
    );
    connect(
        d->ui.sectionFaceTransparencySpin,
        qOverload<int>(&QSpinBox::valueChanged),
        this,
        &SectionAnalysisWidget::onSectionFaceTransparencyChanged
    );
    connect(
        d->ui.showHatchingCheck,
        &QCheckBox::toggled,
        this,
        &SectionAnalysisWidget::onShowHatchingToggled
    );
    connect(
        d->ui.useSectionEdgeColorForHatchingCheck,
        &QCheckBox::toggled,
        this,
        &SectionAnalysisWidget::onUseSectionEdgeColorForHatchingToggled
    );
    connect(
        d->ui.hatchColorButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onHatchColorClicked
    );
    connect(
        d->ui.hatchLineWidthSpin,
        qOverload<double>(&QDoubleSpinBox::valueChanged),
        this,
        &SectionAnalysisWidget::onHatchLineWidthChanged
    );
    connect(
        d->ui.hatchSpacingSpin,
        qOverload<double>(&QDoubleSpinBox::valueChanged),
        this,
        &SectionAnalysisWidget::onHatchSpacingChanged
    );
    connect(
        d->ui.hatchAngleSpin,
        qOverload<double>(&QDoubleSpinBox::valueChanged),
        this,
        &SectionAnalysisWidget::onHatchAngleChanged
    );
}

void SectionAnalysisWidget::onResultModeChanged(int index)
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    analysis->ResultMode.setValue(index);
    if (auto* doc = analysis->getDocument()) {
        doc->recompute();
    }
    refreshResult();
}

void SectionAnalysisWidget::onRecomputeClicked()
{
    auto* analysis = getSectionAnalysis();
    if (!analysis || !analysis->getDocument()) {
        return;
    }

    analysis->getDocument()->recompute();
    refresh();
}

void SectionAnalysisWidget::onUseCurrentSelectionAsSources()
{
    std::vector<App::DocumentObject*> sources = getSelectedSourceObjects();
    if (sources.empty()) {
        refreshSources();
        return;
    }

    setSources(sources);
}

void SectionAnalysisWidget::onAppendCurrentSelectionAsSources()
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    std::vector<App::DocumentObject*> sources = analysis->Sources.getValues();
    std::set<std::string> sourceNames;
    for (auto* source : sources) {
        if (source) {
            sourceNames.insert(source->getNameInDocument());
        }
    }

    bool changed = false;
    for (auto* source : getSelectedSourceObjects()) {
        if (source && sourceNames.insert(source->getNameInDocument()).second) {
            sources.push_back(source);
            changed = true;
        }
    }

    if (changed) {
        setSources(sources);
    }
    else {
        refreshSources();
    }
}

void SectionAnalysisWidget::onRemoveSelectedSources()
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    std::set<std::string> removedNames;
    for (auto* item : d->ui.sourcesList->selectedItems()) {
        removedNames.insert(item->data(Qt::UserRole).toByteArray().constData());
    }

    if (removedNames.empty()) {
        refreshButtons();
        return;
    }

    std::vector<App::DocumentObject*> sources;
    for (auto* source : analysis->Sources.getValues()) {
        if (!source || removedNames.contains(source->getNameInDocument())) {
            continue;
        }
        sources.push_back(source);
    }

    setSources(sources);
}

void SectionAnalysisWidget::onSelectSources()
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    selectObjects(analysis->Sources.getValues());
}

void SectionAnalysisWidget::onActivationToggled(bool on)
{
    auto* plane = getClippingPlane();
    auto* view = getCurrentView();
    if (!plane || !view) {
        refreshActivation();
        return;
    }

    if (on) {
        Gui::ClippingPlaneManager::instance().activate(view, plane);
    }
    else {
        Gui::ClippingPlaneManager::instance().deactivate(view, plane);
    }

    refreshActivation();
}

void SectionAnalysisWidget::onSelectClippingPlane()
{
    auto* plane = getClippingPlane();
    if (!plane) {
        return;
    }

    selectObjects({plane});
}

void SectionAnalysisWidget::onUseCurrentSelectionAsClippingPlane()
{
    if (auto* plane = getSelectedClippingPlane()) {
        setClippingPlane(plane);
    }
    else {
        refreshClippingPlane();
        refreshActivation();
        refreshButtons();
    }
}

void SectionAnalysisWidget::onEditClippingPlaneToggled(bool on)
{
    auto* editor = ensurePlaneEditor();
    auto* planeViewProvider = editor ? editor->getViewProvider() : nullptr;
    auto* view = getCurrentView();
    if (!planeViewProvider || !view) {
        const QSignalBlocker blocker(d->ui.editClippingPlaneButton);
        d->ui.editClippingPlaneButton->setChecked(false);
        return;
    }

    if (!Gui::GizmoContainer::isEnabled()) {
        if (on) {
            const bool started = planeViewProvider->startPanelPlaneEdit(view->getViewer(), [this]() {
                recomputeSectionAnalysisIfReady();
            });
            if (!started) {
                const QSignalBlocker blocker(d->ui.editClippingPlaneButton);
                d->ui.editClippingPlaneButton->setChecked(false);
            }
        }
        else {
            planeViewProvider->finishPanelPlaneEdit();
        }
        refreshButtons();
        return;
    }

    if (on) {
        if (!startDedicatedPlaneGizmoEdit()) {
            const QSignalBlocker blocker(d->ui.editClippingPlaneButton);
            d->ui.editClippingPlaneButton->setChecked(false);
        }
    }
    else {
        finishDedicatedPlaneGizmoEdit(true);
    }

    refreshButtons();
}

void SectionAnalysisWidget::onFlipClippingDirectionToggled(bool on)
{
    auto* plane = getClippingPlane();
    if (!plane) {
        refreshPlane();
        refreshButtons();
        return;
    }

    plane->Reverse.setValue(on);
    queueSectionRecompute();
    refreshActivation();
    refreshButtons();
}

void SectionAnalysisWidget::onPlaneControlsChanged()
{
    auto* editor = ensurePlaneEditor();
    if (!editor) {
        refreshPlane();
        refreshButtons();
        return;
    }

    Gui::PlaneGizmoEditor::State state;
    state.offset = d->ui.planeOffsetSpin->rawValue();
    state.tiltXDegrees = d->ui.planeTiltXSpin->rawValue();
    state.tiltYDegrees = d->ui.planeTiltYSpin->rawValue();
    editor->setState(state, !editor->isActive());
}

void SectionAnalysisWidget::onApplyPlanePreset()
{
    auto* editor = ensurePlaneEditor();
    if (!editor) {
        refreshPlane();
        refreshButtons();
        return;
    }

    const auto preset = static_cast<Gui::PlaneGizmoEditor::Preset>(
        d->ui.planePresetCombo->currentIndex()
    );
    if (preset == Gui::PlaneGizmoEditor::Preset::View && !getCurrentView()) {
        refreshButtons();
        return;
    }

    editor->setPreset(preset, getCurrentView(), !editor->isActive());
}

void SectionAnalysisWidget::onHelperSizeModeChanged(int index)
{
    auto* plane = getClippingPlane();
    auto* clippingPlaneViewProvider = getClippingPlaneViewProvider(getViewProvider(), plane);
    if (!clippingPlaneViewProvider) {
        return;
    }

    clippingPlaneViewProvider->HelperSizeMode.setValue(index);
}

void SectionAnalysisWidget::onFitHelperToSources()
{
    auto* analysis = getSectionAnalysis();
    auto* plane = getClippingPlane();
    auto* view = getCurrentView();
    auto* clippingPlaneViewProvider = getClippingPlaneViewProvider(getViewProvider(), plane);
    if (!analysis || !plane || !clippingPlaneViewProvider) {
        return;
    }

    auto* guiDocument = clippingPlaneViewProvider->getDocument();
    const auto bbox = Gui::ClippingPlaneHelperFit::collectBounds(
        guiDocument,
        view,
        analysis->Sources.getValues(),
        plane
    );
    if (!bbox.IsValid()) {
        return;
    }

    Gui::ClippingPlaneHelperFit::applyFittedHelper(
        clippingPlaneViewProvider,
        currentEditablePlanePlacement(),
        bbox
    );
    refreshPlane();
    refreshButtons();
}

void SectionAnalysisWidget::onFitHelperToSelection()
{
    auto* plane = getClippingPlane();
    auto* view = getCurrentView();
    auto* clippingPlaneViewProvider = getClippingPlaneViewProvider(getViewProvider(), plane);
    if (!plane || !clippingPlaneViewProvider) {
        return;
    }

    auto* guiDocument = clippingPlaneViewProvider->getDocument();
    const auto bbox = Gui::ClippingPlaneHelperFit::collectBounds(
        guiDocument,
        view,
        getSelectedSourceObjects(),
        plane
    );
    if (!bbox.IsValid()) {
        return;
    }

    Gui::ClippingPlaneHelperFit::applyFittedHelper(
        clippingPlaneViewProvider,
        currentEditablePlanePlacement(),
        bbox
    );
    refreshPlane();
    refreshButtons();
}

void SectionAnalysisWidget::onSectionFaceColorClicked()
{
    auto* viewProvider = getViewProvider();
    if (!viewProvider) {
        return;
    }

    const Base::Color current = viewProvider->SectionFaceColor.getValue();
    const QColor initial = QColor::fromRgbF(current.r, current.g, current.b, 1.0);
    const QColor chosen = QColorDialog::getColor(initial, this, tr("Choose section face color"));
    if (!chosen.isValid()) {
        return;
    }

    viewProvider->SectionFaceColor.setValue(Base::Color::fromValue<QColor>(chosen));
    refreshAppearance();
}

void SectionAnalysisWidget::onSectionEdgeColorClicked()
{
    auto* viewProvider = getViewProvider();
    if (!viewProvider) {
        return;
    }

    const Base::Color current = viewProvider->SectionEdgeColor.getValue();
    const QColor initial = QColor::fromRgbF(current.r, current.g, current.b, 1.0);
    const QColor chosen = QColorDialog::getColor(initial, this, tr("Choose section edge color"));
    if (!chosen.isValid()) {
        return;
    }

    viewProvider->SectionEdgeColor.setValue(Base::Color::fromValue<QColor>(chosen));
    refreshAppearance();
}

void SectionAnalysisWidget::onSectionFaceTransparencyChanged(int value)
{
    auto* viewProvider = getViewProvider();
    if (!viewProvider) {
        return;
    }

    viewProvider->SectionFaceTransparency.setValue(value);
}

void SectionAnalysisWidget::onShowHatchingToggled(bool on)
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    analysis->ShowHatching.setValue(on);
    if (auto* doc = analysis->getDocument()) {
        doc->recompute();
    }
    refresh();
}

void SectionAnalysisWidget::onUseSectionEdgeColorForHatchingToggled(bool on)
{
    auto* viewProvider = getViewProvider();
    if (!viewProvider) {
        return;
    }

    viewProvider->UseSectionEdgeColorForHatching.setValue(on);
    refreshAppearance();
    refreshButtons();
}

void SectionAnalysisWidget::onHatchColorClicked()
{
    auto* viewProvider = getViewProvider();
    if (!viewProvider) {
        return;
    }

    const Base::Color current = viewProvider->HatchColor.getValue();
    const QColor initial = QColor::fromRgbF(current.r, current.g, current.b, 1.0);
    const QColor chosen = QColorDialog::getColor(initial, this, tr("Choose hatch color"));
    if (!chosen.isValid()) {
        return;
    }

    viewProvider->HatchColor.setValue(Base::Color::fromValue<QColor>(chosen));
    refreshAppearance();
}

void SectionAnalysisWidget::onHatchLineWidthChanged(double value)
{
    auto* viewProvider = getViewProvider();
    if (!viewProvider) {
        return;
    }

    viewProvider->HatchLineWidth.setValue(static_cast<float>(value));
}

void SectionAnalysisWidget::onHatchSpacingChanged(double value)
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    analysis->HatchSpacing.setValue(value);
    if (auto* doc = analysis->getDocument()) {
        doc->recompute();
    }
    refreshResult();
}

void SectionAnalysisWidget::onHatchAngleChanged(double value)
{
    auto* analysis = getSectionAnalysis();
    if (!analysis) {
        return;
    }

    analysis->HatchAngle.setValue(value);
    if (auto* doc = analysis->getDocument()) {
        doc->recompute();
    }
    refreshResult();
}

void SectionAnalysisWidget::changeEvent(QEvent* event)
{
    QWidget::changeEvent(event);
    if (event->type() == QEvent::LanguageChange) {
        d->ui.retranslateUi(this);
        refresh();
    }
}

TaskSectionAnalysis::TaskSectionAnalysis(ViewProviderSectionAnalysis* viewProvider)
    : widget(new SectionAnalysisWidget(viewProvider))
    , viewProvider(viewProvider)
{
    addTaskBoxWithoutHeader(widget);

    if (viewProvider && viewProvider->getObject()) {
        setDocumentName(viewProvider->getObject()->getDocument()->getName());
        setAutoCloseOnDeletedDocument(true);
        associateToObject3dView(viewProvider->getObject());
    }
}

TaskSectionAnalysis::~TaskSectionAnalysis() = default;

void TaskSectionAnalysis::open()
{
    if (widget) {
        widget->refresh();
    }
    TaskDialog::open();
}

void TaskSectionAnalysis::activate()
{
    if (widget) {
        widget->refresh();
    }
    TaskDialog::activate();
}

bool TaskSectionAnalysis::accept()
{
    return finishEditing() && TaskDialog::accept();
}

bool TaskSectionAnalysis::reject()
{
    return finishEditing() && TaskDialog::reject();
}

bool TaskSectionAnalysis::finishEditing()
{
    if (widget) {
        widget->stopPlaneEditing();
    }

    if (auto* doc = viewProvider ? viewProvider->getDocument() : nullptr) {
        if (doc->hasPendingCommand()) {
            doc->commitCommand();
        }
        doc->resetEdit();
    }

    return true;
}

#include "moc_TaskSectionAnalysis.cpp"
