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

#include <set>

#include <QEvent>
#include <QListWidgetItem>
#include <QSignalBlocker>

#include <TopAbs_ShapeEnum.hxx>
#include <TopExp_Explorer.hxx>

#include <App/ClippingPlane.h>
#include <App/Document.h>
#include <App/DocumentObject.h>
#include <Gui/ClippingPlaneManager.h>
#include <Gui/Document.h>
#include <Gui/Selection/Selection.h>
#include <Gui/View3DInventor.h>

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

}  // namespace

class SectionAnalysisWidget::Private
{
public:
    Ui::SectionAnalysisWidget ui {};
    ViewProviderSectionAnalysis* viewProvider {nullptr};
};

/* TRANSLATOR PartGui::SectionAnalysisWidget */

SectionAnalysisWidget::SectionAnalysisWidget(ViewProviderSectionAnalysis* viewProvider, QWidget* parent)
    : QWidget(parent)
    , d(std::make_unique<Private>())
{
    d->viewProvider = viewProvider;
    d->ui.setupUi(this);
    setupConnections();
    refresh();
}

SectionAnalysisWidget::~SectionAnalysisWidget() = default;

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
    refreshResult();
    refreshActivation();
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
        d->ui.activationStateLabel->setText(
            plane ? tr("No active 3D view is available.")
                  : tr("Link a clipping plane to preview this analysis in a 3D view.")
        );
        return;
    }

    const bool active = Gui::ClippingPlaneManager::instance().isActive(view, plane);
    d->ui.activeInCurrentViewCheck->setChecked(active);
    d->ui.activationStateLabel->setText(
        active ? tr("The linked clipping plane is active in the current 3D view.")
               : tr("The linked clipping plane is inactive in the current 3D view.")
    );
}

void SectionAnalysisWidget::refreshButtons()
{
    const bool hasPlane = getClippingPlane() != nullptr;
    const bool hasSources = getSectionAnalysis()
        && !getSectionAnalysis()->Sources.getValues().empty();
    const bool hasView = getCurrentView() != nullptr;

    d->ui.selectClippingPlaneButton->setEnabled(hasPlane);
    d->ui.editClippingPlaneButton->setEnabled(hasPlane);
    d->ui.selectSourcesButton->setEnabled(hasSources);
    d->ui.recomputeButton->setEnabled(hasPlane && hasSources);
    d->ui.activeInCurrentViewCheck->setEnabled(hasPlane && hasView);
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
        d->ui.editClippingPlaneButton,
        &QPushButton::clicked,
        this,
        &SectionAnalysisWidget::onEditClippingPlane
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
    auto* analysis = getSectionAnalysis();
    if (!analysis || !analysis->getDocument()) {
        return;
    }

    std::vector<App::DocumentObject*> sources;
    std::set<std::string> sourceNames;
    auto* plane = getClippingPlane();
    for (const auto& selected :
         Gui::Selection().getSelection(analysis->getDocument()->getName(), Gui::ResolveMode::NoResolve)) {
        auto* object = selected.pObject;
        if (!object || object == analysis || object == plane
            || object->getDocument() != analysis->getDocument()) {
            continue;
        }
        if (sourceNames.insert(object->getNameInDocument()).second) {
            sources.push_back(object);
        }
    }

    if (sources.empty()) {
        refreshSources();
        return;
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

void SectionAnalysisWidget::onEditClippingPlane()
{
    auto* plane = getClippingPlane();
    auto* sectionViewProvider = getViewProvider();
    auto* doc = sectionViewProvider ? sectionViewProvider->getDocument() : nullptr;
    if (!plane || !doc) {
        return;
    }

    selectObjects({plane});
    if (auto* planeViewProvider = doc->getViewProvider(plane)) {
        doc->setEdit(planeViewProvider, Gui::ViewProvider::Default);
    }
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
    if (auto* doc = viewProvider ? viewProvider->getDocument() : nullptr) {
        if (doc->hasPendingCommand()) {
            doc->commitCommand();
        }
        doc->resetEdit();
    }

    return true;
}

#include "moc_TaskSectionAnalysis.cpp"
