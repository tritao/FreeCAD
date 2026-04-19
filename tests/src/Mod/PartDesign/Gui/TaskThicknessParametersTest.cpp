// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 Joao Matos
// SPDX-FileNotice: Part of the FreeCAD project.

#include <chrono>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

#include <QCoreApplication>
#include <QPointer>
#include <QPushButton>
#include <QTest>

#include <App/Application.h>
#include <App/Document.h>
#include <App/PropertyContainer.h>
#include <Base/Exception.h>
#include <Base/Interpreter.h>
#include <Base/Parameter.h>
#include <Gui/Application.h>
#include <Gui/Control.h>
#include <Gui/DockWindowManager.h>
#include <Gui/Document.h>
#include <Gui/MainWindow.h>
#include <Gui/QuantitySpinBox.h>
#include <Gui/TaskView/TaskDialog.h>
#include <Gui/TaskView/TaskView.h>
#include <Mod/PartDesign/App/Body.h>
#include <Mod/PartDesign/App/FeaturePrimitive.h>
#include <Mod/PartDesign/App/FeatureThickness.h>
#include <Mod/PartDesign/Gui/TaskThicknessParameters.h>
#include <Mod/PartDesign/Gui/ViewProviderThickness.h>

#include <src/App/InitApplication.h>

namespace PartDesign
{

class BlockingThicknessTest: public PartDesign::Thickness
{
    PROPERTY_HEADER_WITH_OVERRIDE(PartDesign::BlockingThicknessTest);

public:
    BlockingThicknessTest() = default;
    ~BlockingThicknessTest() override = default;

    static void resetBlocker();
    static void armBlocker();
    static int getExecutionCount();
    static void releaseBlocker();

    App::DocumentObjectExecReturn* execute() override;
};

}  // namespace PartDesign

namespace
{

struct BlockingThicknessState
{
    std::mutex mutex;
    std::condition_variable changed;
    bool armed = false;
    bool started = false;
    bool proceed = true;
    int executionCount = 0;
    int totalExecutionCount = 0;
};

BlockingThicknessState& getBlockingThicknessState()
{
    static BlockingThicknessState state;
    return state;
}

void resetBlockingThicknessState()
{
    auto& state = getBlockingThicknessState();
    std::lock_guard<std::mutex> lock(state.mutex);
    state.armed = false;
    state.started = false;
    state.proceed = true;
    state.executionCount = 0;
    state.totalExecutionCount = 0;
}

void armBlockingThicknessState()
{
    auto& state = getBlockingThicknessState();
    std::lock_guard<std::mutex> lock(state.mutex);
    state.armed = true;
    state.started = false;
    state.proceed = false;
    state.executionCount = 0;
}

int getBlockingThicknessExecutionCount()
{
    auto& state = getBlockingThicknessState();
    std::lock_guard<std::mutex> lock(state.mutex);
    return state.executionCount;
}

int getBlockingThicknessTotalExecutionCount()
{
    auto& state = getBlockingThicknessState();
    std::lock_guard<std::mutex> lock(state.mutex);
    return state.totalExecutionCount;
}

void releaseBlockingThicknessState()
{
    auto& state = getBlockingThicknessState();
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        state.proceed = true;
    }
    state.changed.notify_all();
}

template<typename ExecuteBase>
App::DocumentObjectExecReturn* executeBlockingThickness(ExecuteBase&& executeBase)
{
    auto& state = getBlockingThicknessState();
    {
        std::unique_lock<std::mutex> lock(state.mutex);
        if (state.armed) {
            state.armed = false;
            state.started = true;
            ++state.executionCount;
            ++state.totalExecutionCount;
            state.changed.notify_all();
            state.changed.wait(lock, [&state] { return state.proceed; });
        }
        else {
            ++state.totalExecutionCount;
        }
    }

    if (App::currentRecomputeWasCanceled()) {
        throw Base::AbortException("User aborted");
    }

    return executeBase();
}

class TestGuiApplication: public Gui::Application
{
public:
    explicit TestGuiApplication(bool guiEnabled)
        : Gui::Application(guiEnabled)
    {}
};

struct GuiHarness
{
    GuiHarness()
        : app(true)
    {
        Gui::Application::initApplication();
        Gui::Application::initOpenInventor();
        Base::Interpreter().runString("import FreeCAD as App\nimport FreeCADGui as Gui");
        Base::Interpreter().runString("import PartDesignGui");
        PartDesign::BlockingThicknessTest::init();

        mainWindow = new Gui::MainWindow();
        mainWindow->hide();

        if (!Gui::DockWindowManager::instance()->getDockWindow("Tasks")) {
            auto* taskView = new Gui::TaskView::TaskView(Gui::getMainWindow());
            taskView->setWindowTitle(QStringLiteral("Tasks"));
            Gui::DockWindowManager::instance()->addDockWindow(
                "Tasks",
                taskView,
                Qt::RightDockWidgetArea
            );
        }
    }

    TestGuiApplication app;
    Gui::MainWindow* mainWindow = nullptr;
};

GuiHarness& ensureGuiHarness()
{
    static GuiHarness harness;
    return harness;
}

template<typename TaskBoxType>
TaskBoxType* findTaskBox(Gui::TaskView::TaskDialog* dialog)
{
    for (QWidget* widget : dialog->getDialogContent()) {
        if (auto* taskBox = qobject_cast<TaskBoxType*>(widget)) {
            return taskBox;
        }
    }

    return nullptr;
}

Gui::QuantitySpinBox* findValueSpinBox(QWidget* taskBox)
{
    return taskBox ? taskBox->findChild<Gui::QuantitySpinBox*>(QStringLiteral("Value")) : nullptr;
}

QPushButton* findCancelPreviewButton(QWidget* taskBox)
{
    return taskBox ? taskBox->findChild<QPushButton*>(QStringLiteral("buttonCancelPreview")) : nullptr;
}

}  // namespace

PROPERTY_SOURCE(PartDesign::BlockingThicknessTest, PartDesign::Thickness)

void PartDesign::BlockingThicknessTest::resetBlocker()
{
    resetBlockingThicknessState();
}

void PartDesign::BlockingThicknessTest::armBlocker()
{
    armBlockingThicknessState();
}

int PartDesign::BlockingThicknessTest::getExecutionCount()
{
    return getBlockingThicknessExecutionCount();
}

void PartDesign::BlockingThicknessTest::releaseBlocker()
{
    releaseBlockingThicknessState();
}

App::DocumentObjectExecReturn* PartDesign::BlockingThicknessTest::execute()
{
    return executeBlockingThickness([this]() { return PartDesign::Thickness::execute(); });
}

class testTaskThicknessParameters final: public QObject
{
    Q_OBJECT

private Q_SLOTS:
    void initTestCase()  // NOLINT
    {
        tests::initApplication();
        Base::Interpreter().runString("import Part");
        Base::Interpreter().runString("import _PartDesign");
        Q_UNUSED(ensureGuiHarness());

        asyncParams = App::GetApplication().GetParameterGroupByPath(
            "User parameter:BaseApp/Preferences/Document"
        );
        oldAsyncEnabled = asyncParams->GetBool("EnableAsyncRecompute", true);
        asyncParams->SetBool("EnableAsyncRecompute", true);

        gizmoParams = App::GetApplication().GetParameterGroupByPath(
            "User parameter:BaseApp/Preferences/Gui/Gizmos"
        );
        oldGizmosEnabled = gizmoParams->GetBool("EnableGizmos", true);
        gizmoParams->SetBool("EnableGizmos", false);
    }

    void cleanupTestCase()  // NOLINT
    {
        if (gizmoParams) {
            gizmoParams->SetBool("EnableGizmos", oldGizmosEnabled);
            gizmoParams = nullptr;
        }
        if (asyncParams) {
            asyncParams->SetBool("EnableAsyncRecompute", oldAsyncEnabled);
            asyncParams = nullptr;
        }
    }

    void init()  // NOLINT
    {
        Q_UNUSED(ensureGuiHarness());

        PartDesign::BlockingThicknessTest::resetBlocker();

        docName = App::GetApplication().getUniqueDocumentName("blocking_thickness_dialog");
        App::DocumentInitFlags initFlags;
        initFlags.createView = false;
        doc = App::GetApplication().newDocument(docName.c_str(), "testUser", initFlags);
        QVERIFY(doc != nullptr);

        guiDoc = Gui::Application::Instance->getDocument(doc);
        QVERIFY(guiDoc != nullptr);

        body = doc->addObject<PartDesign::Body>("Body");
        QVERIFY(body != nullptr);

        baseBox = doc->addObject<PartDesign::AdditiveBox>("BaseBox");
        QVERIFY(baseBox != nullptr);
        body->addObject(baseBox);
        baseBox->Length.setValue(10.0);
        baseBox->Width.setValue(10.0);
        baseBox->Height.setValue(10.0);

        doc->recompute();

        thickness = doc->addObject<PartDesign::BlockingThicknessTest>("BlockingThickness");
        QVERIFY(thickness != nullptr);
        body->addObject(thickness);
        thickness->Base.setValue(baseBox, {"Face1"});
        thickness->Value.setValue(1.0);
        thickness->Reversed.setValue(true);
        thickness->Mode.setValue(0L);
        thickness->Join.setValue(0L);

        doc->recompute();

        thicknessView = dynamic_cast<PartDesignGui::ViewProviderThickness*>(guiDoc->getViewProvider(thickness));
        QVERIFY(thicknessView != nullptr);

        guiDoc->openCommand("Edit blocking thickness");
        PartDesign::BlockingThicknessTest::resetBlocker();
    }

    void cleanup()  // NOLINT
    {
        PartDesign::BlockingThicknessTest::releaseBlocker();
        QCoreApplication::processEvents();

        if (doc && Gui::Control().activeDialog(doc)) {
            Gui::Control().closeDialog(doc);
            QCoreApplication::processEvents();
        }

        if (!docName.empty() && App::GetApplication().getDocument(docName.c_str())) {
            App::GetApplication().closeDocument(docName.c_str());
        }

        thicknessView = nullptr;
        thickness = nullptr;
        baseBox = nullptr;
        body = nullptr;
        guiDoc = nullptr;
        doc = nullptr;
        docName.clear();
    }

    void thicknessRejectDefersCloseUntilAsyncPreviewSettles()  // NOLINT
    {
        auto* dialog = new PartDesignGui::TaskDlgThicknessParameters(thicknessView);
        QPointer<PartDesignGui::TaskDlgThicknessParameters> guard(dialog);
        Gui::Control().showDialog(dialog, doc);
        QCoreApplication::processEvents();

        auto* taskBox = findTaskBox<PartDesignGui::TaskThicknessParameters>(dialog);
        QVERIFY(taskBox != nullptr);

        auto* value = findValueSpinBox(taskBox);
        QVERIFY(value != nullptr);

        PartDesign::BlockingThicknessTest::armBlocker();
        value->setValue(value->rawValue() + 0.5);
        QCoreApplication::processEvents();

        QTRY_COMPARE_WITH_TIMEOUT(PartDesign::BlockingThicknessTest::getExecutionCount(), 1, 3000);
        QVERIFY(taskBox->hasOutstandingRecompute());

        Gui::Control().reject(doc);

        QCOMPARE(
            Gui::Control().activeDialog(doc),
            static_cast<Gui::TaskView::TaskDialog*>(dialog)
        );
        QVERIFY(taskBox->hasOutstandingRecompute());
        QVERIFY(guiDoc->hasPendingCommand());

        PartDesign::BlockingThicknessTest::releaseBlocker();

        QTRY_VERIFY_WITH_TIMEOUT(guard.isNull(), 3000);
        QCOMPARE(Gui::Control().activeDialog(doc), nullptr);
        QVERIFY(!guiDoc->hasPendingCommand());
    }

    void thicknessCancelPreviewStopsAsyncRunWithoutClosingDialog()  // NOLINT
    {
        auto* dialog = new PartDesignGui::TaskDlgThicknessParameters(thicknessView);
        QPointer<PartDesignGui::TaskDlgThicknessParameters> guard(dialog);
        Gui::Control().showDialog(dialog, doc);
        QCoreApplication::processEvents();

        auto* taskBox = findTaskBox<PartDesignGui::TaskThicknessParameters>(dialog);
        QVERIFY(taskBox != nullptr);

        auto* value = findValueSpinBox(taskBox);
        QVERIFY(value != nullptr);

        auto* cancelPreview = findCancelPreviewButton(taskBox);
        QVERIFY(cancelPreview != nullptr);

        PartDesign::BlockingThicknessTest::armBlocker();
        value->setValue(value->rawValue() + 0.5);
        QCoreApplication::processEvents();

        QTRY_COMPARE_WITH_TIMEOUT(PartDesign::BlockingThicknessTest::getExecutionCount(), 1, 3000);
        QVERIFY(taskBox->hasOutstandingRecompute());
        QVERIFY(cancelPreview->isEnabled());

        cancelPreview->click();
        QCoreApplication::processEvents();

        QVERIFY(taskBox->hasOutstandingRecompute());
        QCOMPARE(
            Gui::Control().activeDialog(doc),
            static_cast<Gui::TaskView::TaskDialog*>(dialog)
        );

        PartDesign::BlockingThicknessTest::releaseBlocker();

        QTRY_VERIFY_WITH_TIMEOUT(!taskBox->hasOutstandingRecompute(), 3000);
        QVERIFY(!guard.isNull());
        QCOMPARE(
            Gui::Control().activeDialog(doc),
            static_cast<Gui::TaskView::TaskDialog*>(dialog)
        );
        QCOMPARE(PartDesign::BlockingThicknessTest::getExecutionCount(), 1);
    }

    void thicknessAcceptWaitsForQueuedPreviewWithoutExtraRerun()  // NOLINT
    {
        auto* dialog = new PartDesignGui::TaskDlgThicknessParameters(thicknessView);
        QPointer<PartDesignGui::TaskDlgThicknessParameters> guard(dialog);
        Gui::Control().showDialog(dialog, doc);
        QCoreApplication::processEvents();

        auto* taskBox = findTaskBox<PartDesignGui::TaskThicknessParameters>(dialog);
        QVERIFY(taskBox != nullptr);
        QTRY_VERIFY_WITH_TIMEOUT(!taskBox->hasOutstandingRecompute(), 3000);

        auto* value = findValueSpinBox(taskBox);
        QVERIFY(value != nullptr);

        PartDesign::BlockingThicknessTest::armBlocker();
        value->setValue(value->rawValue() + 0.5);
        QCoreApplication::processEvents();

        QTRY_COMPARE_WITH_TIMEOUT(PartDesign::BlockingThicknessTest::getExecutionCount(), 1, 3000);
        QCOMPARE(getBlockingThicknessTotalExecutionCount(), 1);
        QVERIFY(taskBox->hasOutstandingRecompute());

        value->setValue(value->rawValue() + 0.5);
        QCoreApplication::processEvents();
        QVERIFY(taskBox->hasOutstandingRecompute());

        std::thread releaser([]() {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
            PartDesign::BlockingThicknessTest::releaseBlocker();
        });

        std::string acceptError;
        try {
            Gui::Control().accept(doc);
        }
        catch (const Base::Exception& e) {
            acceptError = e.what();
        }
        catch (const std::exception& e) {
            acceptError = e.what();
        }
        catch (...) {
            acceptError = "unknown exception";
        }
        releaser.join();
        QVERIFY2(acceptError.empty(), acceptError.c_str());

        QTRY_VERIFY_WITH_TIMEOUT(guard.isNull(), 3000);
        QCOMPARE(Gui::Control().activeDialog(doc), nullptr);
        QVERIFY(!guiDoc->hasPendingCommand());
        QCOMPARE(getBlockingThicknessTotalExecutionCount(), 2);
    }

private:
    Base::Reference<ParameterGrp> asyncParams;
    bool oldAsyncEnabled = true;
    Base::Reference<ParameterGrp> gizmoParams;
    bool oldGizmosEnabled = true;
    std::string docName;
    App::Document* doc = nullptr;
    Gui::Document* guiDoc = nullptr;
    PartDesign::Body* body = nullptr;
    PartDesign::AdditiveBox* baseBox = nullptr;
    PartDesign::BlockingThicknessTest* thickness = nullptr;
    PartDesignGui::ViewProviderThickness* thicknessView = nullptr;
};

extern "C" Q_DECL_EXPORT int runTaskThicknessParametersTest(int argc, char** argv)
{
    testTaskThicknessParameters test;
    return QTest::qExec(&test, argc, argv);
}

#include "TaskThicknessParametersTest.moc"
