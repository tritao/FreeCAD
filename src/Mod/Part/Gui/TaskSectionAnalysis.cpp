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

#include <QColor>
#include <QColorDialog>
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

void SectionAnalysisWidget::refreshAppearance()
{
    auto* viewProvider = getViewProvider();
    if (!viewProvider) {
        return;
    }

    setColorButtonPreview(d->ui.sectionFaceColorButton, viewProvider->SectionFaceColor.getValue());
    setColorButtonPreview(d->ui.sectionEdgeColorButton, viewProvider->SectionEdgeColor.getValue());

    const QSignalBlocker transparencyBlocker(d->ui.sectionFaceTransparencySpin);
    d->ui.sectionFaceTransparencySpin->setValue(viewProvider->SectionFaceTransparency.getValue());

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
    const bool hasPlane = getClippingPlane() != nullptr;
    auto* analysis = getSectionAnalysis();
    const bool hasSources = analysis && !analysis->Sources.getValues().empty();
    const bool hasView = getCurrentView() != nullptr;
    const bool hatchEnabled = analysis && analysis->ShowHatching.getValue();

    d->ui.selectClippingPlaneButton->setEnabled(hasPlane);
    d->ui.editClippingPlaneButton->setEnabled(hasPlane);
    d->ui.selectSourcesButton->setEnabled(hasSources);
    d->ui.recomputeButton->setEnabled(hasPlane && hasSources);
    d->ui.activeInCurrentViewCheck->setEnabled(hasPlane && hasView);
    d->ui.showHatchingCheck->setEnabled(hasSources);
    d->ui.hatchSpacingSpin->setEnabled(hasSources && hatchEnabled);
    d->ui.hatchAngleSpin->setEnabled(hasSources && hatchEnabled);
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
    if (auto* doc = viewProvider ? viewProvider->getDocument() : nullptr) {
        if (doc->hasPendingCommand()) {
            doc->commitCommand();
        }
        doc->resetEdit();
    }

    return true;
}

#include "moc_TaskSectionAnalysis.cpp"
