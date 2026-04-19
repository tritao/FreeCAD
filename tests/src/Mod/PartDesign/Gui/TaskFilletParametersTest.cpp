// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 Joao Matos
// SPDX-FileNotice: Part of the FreeCAD project.

#include <chrono>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

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
#include <Mod/PartDesign/App/FeatureFillet.h>
#include <Mod/PartDesign/App/FeaturePrimitive.h>
#include <Mod/PartDesign/Gui/TaskFilletParameters.h>
#include <Mod/PartDesign/Gui/ViewProviderFillet.h>

#include <src/App/InitApplication.h>

namespace PartDesign
{

class BlockingFilletTest: public PartDesign::Fillet
{
    PROPERTY_HEADER_WITH_OVERRIDE(PartDesign::BlockingFilletTest);

public:
    BlockingFilletTest() = default;
    ~BlockingFilletTest() override = default;

    static void resetBlocker();
    static void armBlocker();
    static int getExecutionCount();
    static void releaseBlocker();

    App::DocumentObjectExecReturn* execute() override;
};

}  // namespace PartDesign

namespace
{

struct BlockingFilletState
{
    std::mutex mutex;
    std::condition_variable changed;
    bool armed = false;
    bool started = false;
    bool proceed = true;
    int executionCount = 0;
    int totalExecutionCount = 0;
};

BlockingFilletState& getBlockingFilletState()
{
    static BlockingFilletState state;
    return state;
}

void resetBlockingFilletState()
{
    auto& state = getBlockingFilletState();
    std::lock_guard<std::mutex> lock(state.mutex);
    state.armed = false;
    state.started = false;
    state.proceed = true;
    state.executionCount = 0;
    state.totalExecutionCount = 0;
}

void armBlockingFilletState()
{
    auto& state = getBlockingFilletState();
    std::lock_guard<std::mutex> lock(state.mutex);
    state.armed = true;
    state.started = false;
    state.proceed = false;
    state.executionCount = 0;
}

int getBlockingFilletExecutionCount()
{
    auto& state = getBlockingFilletState();
    std::lock_guard<std::mutex> lock(state.mutex);
    return state.executionCount;
}

int getBlockingFilletTotalExecutionCount()
{
    auto& state = getBlockingFilletState();
    std::lock_guard<std::mutex> lock(state.mutex);
    return state.totalExecutionCount;
}

void releaseBlockingFilletState()
{
    auto& state = getBlockingFilletState();
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        state.proceed = true;
    }
    state.changed.notify_all();
}

template<typename ExecuteBase>
App::DocumentObjectExecReturn* executeBlockingFillet(ExecuteBase&& executeBase)
{
    auto& state = getBlockingFilletState();
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
        PartDesign::BlockingFilletTest::init();

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

Gui::QuantitySpinBox* findRadiusSpinBox(QWidget* taskBox)
{
    return taskBox ? taskBox->findChild<Gui::QuantitySpinBox*>(QStringLiteral("filletRadius"))
                   : nullptr;
}

QPushButton* findCancelPreviewButton(QWidget* taskBox)
{
    return taskBox ? taskBox->findChild<QPushButton*>(QStringLiteral("buttonCancelPreview")) : nullptr;
}

std::vector<std::string> allBoxFaces()
{
    return {"Face1", "Face2", "Face3", "Face4", "Face5", "Face6"};
}

}  // namespace

PROPERTY_SOURCE(PartDesign::BlockingFilletTest, PartDesign::Fillet)

void PartDesign::BlockingFilletTest::resetBlocker()
{
    resetBlockingFilletState();
}

void PartDesign::BlockingFilletTest::armBlocker()
{
    armBlockingFilletState();
}

int PartDesign::BlockingFilletTest::getExecutionCount()
{
    return getBlockingFilletExecutionCount();
}

void PartDesign::BlockingFilletTest::releaseBlocker()
{
    releaseBlockingFilletState();
}

App::DocumentObjectExecReturn* PartDesign::BlockingFilletTest::execute()
{
    return executeBlockingFillet([this]() { return PartDesign::Fillet::execute(); });
}

class testTaskFilletParameters final: public QObject
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

        PartDesign::BlockingFilletTest::resetBlocker();

        docName = App::GetApplication().getUniqueDocumentName("blocking_fillet_dialog");
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

        fillet = doc->addObject<PartDesign::BlockingFilletTest>("BlockingFillet");
        QVERIFY(fillet != nullptr);
        body->addObject(fillet);
        fillet->Base.setValue(baseBox, allBoxFaces());
        fillet->Radius.setValue(1.0);
        fillet->UseAllEdges.setValue(false);

        doc->recompute();

        filletView = dynamic_cast<PartDesignGui::ViewProviderFillet*>(guiDoc->getViewProvider(fillet));
        QVERIFY(filletView != nullptr);

        guiDoc->openCommand("Edit blocking fillet");
        PartDesign::BlockingFilletTest::resetBlocker();
    }

    void cleanup()  // NOLINT
    {
        PartDesign::BlockingFilletTest::releaseBlocker();
        QCoreApplication::processEvents();

        if (doc && Gui::Control().activeDialog(doc)) {
            Gui::Control().closeDialog(doc);
            QCoreApplication::processEvents();
        }

        if (!docName.empty() && App::GetApplication().getDocument(docName.c_str())) {
            App::GetApplication().closeDocument(docName.c_str());
        }

        filletView = nullptr;
        fillet = nullptr;
        baseBox = nullptr;
        body = nullptr;
        guiDoc = nullptr;
        doc = nullptr;
        docName.clear();
    }

    void filletRejectDefersCloseUntilAsyncPreviewSettles()  // NOLINT
    {
        auto* dialog = new PartDesignGui::TaskDlgFilletParameters(filletView);
        QPointer<PartDesignGui::TaskDlgFilletParameters> guard(dialog);
        Gui::Control().showDialog(dialog, doc);
        QCoreApplication::processEvents();

        auto* taskBox = findTaskBox<PartDesignGui::TaskFilletParameters>(dialog);
        QVERIFY(taskBox != nullptr);

        auto* radius = findRadiusSpinBox(taskBox);
        QVERIFY(radius != nullptr);

        PartDesign::BlockingFilletTest::armBlocker();
        radius->setValue(radius->rawValue() + 0.5);
        QCoreApplication::processEvents();

        QTRY_COMPARE_WITH_TIMEOUT(PartDesign::BlockingFilletTest::getExecutionCount(), 1, 3000);
        QVERIFY(taskBox->hasOutstandingRecompute());

        Gui::Control().reject(doc);

        QCOMPARE(
            Gui::Control().activeDialog(doc),
            static_cast<Gui::TaskView::TaskDialog*>(dialog)
        );
        QVERIFY(taskBox->hasOutstandingRecompute());
        QVERIFY(guiDoc->hasPendingCommand());

        PartDesign::BlockingFilletTest::releaseBlocker();

        QTRY_VERIFY_WITH_TIMEOUT(guard.isNull(), 3000);
        QCOMPARE(Gui::Control().activeDialog(doc), nullptr);
        QVERIFY(!guiDoc->hasPendingCommand());
    }

    void filletCancelPreviewStopsAsyncRunWithoutClosingDialog()  // NOLINT
    {
        auto* dialog = new PartDesignGui::TaskDlgFilletParameters(filletView);
        QPointer<PartDesignGui::TaskDlgFilletParameters> guard(dialog);
        Gui::Control().showDialog(dialog, doc);
        QCoreApplication::processEvents();

        auto* taskBox = findTaskBox<PartDesignGui::TaskFilletParameters>(dialog);
        QVERIFY(taskBox != nullptr);

        auto* radius = findRadiusSpinBox(taskBox);
        QVERIFY(radius != nullptr);

        auto* cancelPreview = findCancelPreviewButton(taskBox);
        QVERIFY(cancelPreview != nullptr);

        PartDesign::BlockingFilletTest::armBlocker();
        radius->setValue(radius->rawValue() + 0.5);
        QCoreApplication::processEvents();

        QTRY_COMPARE_WITH_TIMEOUT(PartDesign::BlockingFilletTest::getExecutionCount(), 1, 3000);
        QVERIFY(taskBox->hasOutstandingRecompute());
        QVERIFY(cancelPreview->isEnabled());

        cancelPreview->click();
        QCoreApplication::processEvents();

        QVERIFY(taskBox->hasOutstandingRecompute());
        QCOMPARE(
            Gui::Control().activeDialog(doc),
            static_cast<Gui::TaskView::TaskDialog*>(dialog)
        );

        PartDesign::BlockingFilletTest::releaseBlocker();

        QTRY_VERIFY_WITH_TIMEOUT(!taskBox->hasOutstandingRecompute(), 3000);
        QVERIFY(!guard.isNull());
        QCOMPARE(
            Gui::Control().activeDialog(doc),
            static_cast<Gui::TaskView::TaskDialog*>(dialog)
        );
        QCOMPARE(PartDesign::BlockingFilletTest::getExecutionCount(), 1);
    }

    void filletAcceptWaitsForQueuedPreviewWithoutExtraRerun()  // NOLINT
    {
        auto* dialog = new PartDesignGui::TaskDlgFilletParameters(filletView);
        QPointer<PartDesignGui::TaskDlgFilletParameters> guard(dialog);
        Gui::Control().showDialog(dialog, doc);
        QCoreApplication::processEvents();

        auto* taskBox = findTaskBox<PartDesignGui::TaskFilletParameters>(dialog);
        QVERIFY(taskBox != nullptr);
        QTRY_VERIFY_WITH_TIMEOUT(!taskBox->hasOutstandingRecompute(), 3000);

        auto* radius = findRadiusSpinBox(taskBox);
        QVERIFY(radius != nullptr);

        PartDesign::BlockingFilletTest::armBlocker();
        radius->setValue(radius->rawValue() + 0.5);
        QCoreApplication::processEvents();

        QTRY_COMPARE_WITH_TIMEOUT(PartDesign::BlockingFilletTest::getExecutionCount(), 1, 3000);
        QCOMPARE(getBlockingFilletTotalExecutionCount(), 1);
        QVERIFY(taskBox->hasOutstandingRecompute());

        radius->setValue(radius->rawValue() + 0.5);
        QCoreApplication::processEvents();
        QVERIFY(taskBox->hasOutstandingRecompute());

        std::thread releaser([]() {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
            PartDesign::BlockingFilletTest::releaseBlocker();
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
        QCOMPARE(getBlockingFilletTotalExecutionCount(), 2);
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
    PartDesign::BlockingFilletTest* fillet = nullptr;
    PartDesignGui::ViewProviderFillet* filletView = nullptr;
};

extern "C" Q_DECL_EXPORT int runTaskFilletParametersTest(int argc, char** argv)
{
    testTaskFilletParameters test;
    return QTest::qExec(&test, argc, argv);
}

#include "TaskFilletParametersTest.moc"
