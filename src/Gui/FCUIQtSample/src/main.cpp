#include "FCUIQtRuntime.h"
#include "FCUIQtHost.h"

#include <QApplication>
#include <QComboBox>
#include <QDockWidget>
#include <QFormLayout>
#include <QGroupBox>
#include <QCheckBox>
#include <QDebug>
#include <QFrame>
#include <QLabel>
#include <QLineEdit>
#include <QMainWindow>
#include <QMessageBox>
#include <QScreen>
#include <QSpinBox>
#include <QStatusBar>
#include <QToolBar>
#include <QTimer>
#include <QVBoxLayout>

class MockHost final : public FCUIQtHost {
    Q_OBJECT

public:
    explicit MockHost(QObject* parent = nullptr) : FCUIQtHost(parent) {
        paths_.insert("selection.count", 0);
    }

    QVariant readPath(const QString& path) const override {
        return paths_.value(path);
    }

    QWidget* createNativeWidget(const QString& kind, const QVariantMap& props, QWidget* parent) override {
        Q_UNUSED(props);
        auto* frame = new QFrame(parent);
        frame->setFrameShape(QFrame::StyledPanel);
        frame->setMinimumSize(320, 240);
        frame->setStyleSheet("background: #20242a; color: #d9e1ee;");

        auto* v = new QVBoxLayout(frame);
        v->setContentsMargins(12, 12, 12, 12);
        v->setSpacing(8);

        const QString id = props.value("id").toString();
        auto* title = new QLabel(id.isEmpty() ? kind : (kind + " — " + id));
        QFont f = title->font();
        f.setPointSize(f.pointSize() + 1);
        f.setBold(true);
        title->setFont(f);
        v->addWidget(title);

        auto* hint = new QLabel("Mock native widget (host-provided QWidget).");
        hint->setWordWrap(true);
        hint->setStyleSheet("color: #aeb8c7;");
        v->addWidget(hint);

        auto* footer = new QLabel("Replace this in FreeCAD host with the real 3D view / panels.");
        footer->setWordWrap(true);
        footer->setStyleSheet("color: #7f8a9b;");
        v->addWidget(footer);
        v->addStretch(1);

        return frame;
    }

    void setPath(const QString& path, const QVariant& value) {
        if (paths_.value(path) == value) {
            return;
        }
        paths_.insert(path, value);
        emit pathChanged(path, value);
    }

public slots:
    void invokeCommand(const QString& name, const QVariantList& args) override {
        Q_UNUSED(args);
        qDebug() << "FCUI command:" << name;
    }

private:
    QVariantMap paths_;
};

int main(int argc, char** argv) {
    QApplication app(argc, argv);

    if (argc < 2) {
        QMessageBox::critical(
            nullptr,
            "fcui_qt_viewer",
            "Usage: fcui_qt_viewer <module.fcuim.json> [ComponentName] [--validate]"
        );
        return 2;
    }

    const QString modulePath = QString::fromLocal8Bit(argv[1]);
    QString requestedComponent;
    bool validateOnly = false;

    for (int i = 2; i < argc; i++) {
        const QString a = QString::fromLocal8Bit(argv[i]);
        if (a == "--validate") {
            validateOnly = true;
            continue;
        }
        if (requestedComponent.isEmpty()) {
            requestedComponent = a;
        }
    }

    MockHost host;
    FCUIQtRuntime runtime(&host);
    QString error;
    if (!runtime.loadModuleFile(modulePath, &error)) {
        QMessageBox::critical(nullptr, "fcui_qt_viewer", error);
        return 2;
    }

    const QString component = !requestedComponent.isEmpty() ? requestedComponent : runtime.componentNames().value(0);
    QWidget* ui = runtime.instantiate(component, &error);
    if (!ui) {
        QMessageBox::critical(nullptr, "fcui_qt_viewer", error);
        return 2;
    }

    QMainWindow win;

    if (validateOnly) {
        runtime.setPropValue("title", "Validate");
        runtime.setPropValue("count", 2);
        host.setPath("selection.count", 7);
        runtime.flushNow();
        delete ui;
        return 0;
    }

    auto* controls = new QGroupBox("Props (viewer-only)");
    auto* form = new QFormLayout(controls);

    auto* title = new QLineEdit();
    title->setText(runtime.propValue("title").toString());
    form->addRow("title", title);
    QObject::connect(title, &QLineEdit::textChanged, &runtime, [&runtime](const QString& t) {
        runtime.setPropValue("title", t);
    });

    auto* count = new QSpinBox();
    count->setRange(0, 999999);
    count->setValue(runtime.propValue("count").toInt());
    form->addRow("count", count);
    QObject::connect(
        count,
        static_cast<void (QSpinBox::*)(int)>(&QSpinBox::valueChanged),
        &runtime,
        [&runtime](int v) {
        runtime.setPropValue("count", v);
        }
    );

    auto* hostSel = new QLabel(QString::number(host.readPath("selection.count").toInt()));
    form->addRow("fc.selection.count", hostSel);
    QObject::connect(&host, &FCUIQtHost::pathChanged, hostSel, [hostSel](const QString& path, const QVariant& value) {
        if (path == "selection.count") {
            hostSel->setText(QString::number(value.toInt()));
        }
    });

    auto* tickSel = new QCheckBox("tick");
    form->addRow("mock selection", tickSel);

    auto* tickTimer = new QTimer(&win);
    tickTimer->setInterval(500);
    QObject::connect(tickTimer, &QTimer::timeout, &host, [&host]() {
        int v = host.readPath("selection.count").toInt();
        v = (v + 1) % 11;
        host.setPath("selection.count", v);
    });
    QObject::connect(tickSel, &QCheckBox::toggled, tickTimer, [tickTimer](bool on) {
        if (on) {
            tickTimer->start();
        } else {
            tickTimer->stop();
        }
    });

    auto* central = new QWidget();
    auto* layout = new QVBoxLayout(central);
    layout->addWidget(controls);

    // Promote any Dock nodes to QDockWidget on the QMainWindow.
    QList<QDockWidget*> leftDocks;
    QList<int> leftSizes;
    QList<QDockWidget*> rightDocks;
    QList<int> rightSizes;
    QList<QDockWidget*> topDocks;
    QList<int> topSizes;
    QList<QDockWidget*> bottomDocks;
    QList<int> bottomSizes;

    {
        const auto dockRoots = ui->findChildren<QWidget*>(QString(), Qt::FindChildrenRecursively);
        for (QWidget* dockRoot : dockRoots) {
            const QVariant areaV = dockRoot->property("fcui.dock.area");
            if (!areaV.isValid()) {
                continue;
            }

            const QString areaS = areaV.toString().toLower().trimmed();
            const QString title = dockRoot->property("fcui.dock.title").toString();

            Qt::DockWidgetArea area = Qt::LeftDockWidgetArea;
            if (areaS == "right") {
                area = Qt::RightDockWidgetArea;
            } else if (areaS == "bottom") {
                area = Qt::BottomDockWidgetArea;
            } else if (areaS == "top") {
                area = Qt::TopDockWidgetArea;
            }

            if (dockRoot->parentWidget() && dockRoot->parentWidget()->layout()) {
                dockRoot->parentWidget()->layout()->removeWidget(dockRoot);
            }
            dockRoot->setParent(nullptr);

            auto* dock = new QDockWidget(title.isEmpty() ? "Dock" : title, &win);
            dock->setWidget(dockRoot);
            dock->setObjectName(QString("fcuiDock_%1").arg(title));
            win.addDockWidget(area, dock);

            const QVariant sizeV = dockRoot->property("fcui.dock.size");
            const int size = sizeV.isValid() ? sizeV.toInt() : -1;
            if (area == Qt::LeftDockWidgetArea) {
                leftDocks.push_back(dock);
                leftSizes.push_back(size > 0 ? size : 280);
            } else if (area == Qt::RightDockWidgetArea) {
                rightDocks.push_back(dock);
                rightSizes.push_back(size > 0 ? size : 340);
            } else if (area == Qt::TopDockWidgetArea) {
                topDocks.push_back(dock);
                topSizes.push_back(size > 0 ? size : 120);
            } else if (area == Qt::BottomDockWidgetArea) {
                bottomDocks.push_back(dock);
                bottomSizes.push_back(size > 0 ? size : 160);
            }
        }
    }

    // Promote any ToolBar nodes to QToolBar on the QMainWindow.
    {
        const auto tbRoots = ui->findChildren<QWidget*>(QString(), Qt::FindChildrenRecursively);
        for (QWidget* tbRoot : tbRoots) {
            const QVariant areaV = tbRoot->property("fcui.toolbar.area");
            if (!areaV.isValid()) {
                continue;
            }

            const QString areaS = areaV.toString().toLower().trimmed();
            const QString title = tbRoot->property("fcui.toolbar.title").toString();

            Qt::ToolBarArea area = Qt::TopToolBarArea;
            if (areaS == "left") {
                area = Qt::LeftToolBarArea;
            } else if (areaS == "right") {
                area = Qt::RightToolBarArea;
            } else if (areaS == "bottom") {
                area = Qt::BottomToolBarArea;
            }

            if (tbRoot->parentWidget() && tbRoot->parentWidget()->layout()) {
                tbRoot->parentWidget()->layout()->removeWidget(tbRoot);
            }

            auto* tb = new QToolBar(title.isEmpty() ? "Toolbar" : title, &win);
            tb->setObjectName(QString("fcuiToolBar_%1").arg(title));
            tb->setMovable(true);
            tb->setFloatable(true);

            // Transfer widgets into the QToolBar.
            if (auto* box = qobject_cast<QBoxLayout*>(tbRoot->layout())) {
                while (box->count() > 0) {
                    QLayoutItem* item = box->takeAt(0);
                    QWidget* w = item ? item->widget() : nullptr;
                    delete item;
                    if (!w) {
                        continue;
                    }

                    // Treat our Separator node (QFrame HLine) as a real toolbar separator.
                    if (auto* f = qobject_cast<QFrame*>(w)) {
                        if (f->frameShape() == QFrame::HLine) {
                            delete f;
                            tb->addSeparator();
                            continue;
                        }
                    }

                    w->setParent(nullptr);
                    tb->addWidget(w);
                }
            }

            tbRoot->deleteLater();
            win.addToolBar(area, tb);
        }
    }

    // If the component produced a StatusBar node, promote it to QMainWindow status bar.
    if (auto* box = qobject_cast<QBoxLayout*>(ui->layout())) {
        if (box->count() > 0) {
            if (auto* sb = qobject_cast<QStatusBar*>(box->itemAt(box->count() - 1)->widget())) {
                box->removeWidget(sb);
                sb->setParent(&win);
                win.setStatusBar(sb);
                sb->show();
            }
        }
    }
    layout->addWidget(ui, 1);

    win.setWindowTitle(QString("FCUI Qt Viewer — %1").arg(component));
    win.setCentralWidget(central);

    const QScreen* screen = QGuiApplication::primaryScreen();
    const QSize avail = screen ? screen->availableGeometry().size() : QSize(1200, 800);
    const QSize maxSize(avail.width() * 9 / 10, avail.height() * 9 / 10);

    QSize ideal = central->sizeHint();
    if (!ideal.isValid() || ideal.isEmpty()) {
        ideal = QSize(900, 600);
    }
    ideal = ideal.expandedTo(QSize(720, 480)) + QSize(80, 80);

    auto maxList = [](const QList<int>& xs) -> int {
        int m = 0;
        for (int v : xs) {
            m = std::max(m, v);
        }
        return m;
    };
    const int wantLeft = maxList(leftSizes);
    const int wantRight = maxList(rightSizes);
    const int wantTop = maxList(topSizes);
    const int wantBottom = maxList(bottomSizes);
    if (wantLeft || wantRight || wantTop || wantBottom) {
        // Ensure the window is wide/tall enough to actually honor requested dock sizes.
        ideal.setWidth(std::max(ideal.width(), wantLeft + wantRight + 720));
        ideal.setHeight(std::max(ideal.height(), wantTop + wantBottom + 480));
    }

    ideal.setWidth(std::min(ideal.width(), maxSize.width()));
    ideal.setHeight(std::min(ideal.height(), maxSize.height()));

    win.resize(ideal);
    win.show();

    // Apply dock sizes after the window lays out the dock areas.
    QTimer::singleShot(0, &win, [&win, leftDocks, leftSizes, rightDocks, rightSizes, topDocks, topSizes, bottomDocks, bottomSizes]() {
        if (!leftDocks.isEmpty()) {
            win.resizeDocks(leftDocks, leftSizes, Qt::Horizontal);
        }
        if (!rightDocks.isEmpty()) {
            win.resizeDocks(rightDocks, rightSizes, Qt::Horizontal);
        }
        if (!topDocks.isEmpty()) {
            win.resizeDocks(topDocks, topSizes, Qt::Vertical);
        }
        if (!bottomDocks.isEmpty()) {
            win.resizeDocks(bottomDocks, bottomSizes, Qt::Vertical);
        }
    });

    return app.exec();
}

#include "main.moc"
