#include "FCUIQtRuntime.h"

#include "FCUIQtHost.h"
#include "VmEval.h"

#include <QBoxLayout>
#include <QCheckBox>
#include <QDebug>
#include <QFile>
#include <QFrame>
#include <QGroupBox>
#include <QJsonDocument>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QSet>
#include <QScrollArea>
#include <QSizePolicy>
#include <QSpinBox>
#include <QSplitter>
#include <QStatusBar>
#include <QTabBar>
#include <QTabWidget>
#include <QVariantMap>

#include <limits>

namespace {

QJsonObject readJsonObjectFile(const QString& path, QString* errorMessage) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) {
        if (errorMessage) {
            *errorMessage = QString("failed to open '%1': %2").arg(path, f.errorString());
        }
        return {};
    }

    const auto doc = QJsonDocument::fromJson(f.readAll());
    if (!doc.isObject()) {
        if (errorMessage) {
            *errorMessage = QString("invalid JSON object in '%1'").arg(path);
        }
        return {};
    }
    return doc.object();
}

QJsonObject asObject(const QJsonValue& v) {
    return v.isObject() ? v.toObject() : QJsonObject{};
}

QJsonArray asArray(const QJsonValue& v) {
    return v.isArray() ? v.toArray() : QJsonArray{};
}

struct BindingDeps {
    QSet<QString> selfDeps;
    QSet<QString> hostDeps;
};

BindingDeps depsFromOps(const QJsonArray& ops) {
    BindingDeps d;
    for (const auto& insVal : ops) {
        const auto ins = insVal.toObject();
        const auto op = ins.value("op").toString();
        if (op == "LOAD_SELF") {
            d.selfDeps.insert(ins.value("name").toString());
        } else if (op == "LOAD_HOST_PATH") {
            d.hostDeps.insert(ins.value("path").toString());
        }
    }
    return d;
}

} // namespace

FCUIQtRuntime::FCUIQtRuntime(FCUIQtHost* host, QObject* parent)
    : QObject(parent), vm_(std::make_unique<VmEval>()) {
    refreshTimer_ = new QTimer(this);
    refreshTimer_->setSingleShot(true);
    refreshTimer_->setInterval(0);
    connect(refreshTimer_, &QTimer::timeout, this, [this]() { flushPendingUpdates(); });

    setHost(host);
}

FCUIQtRuntime::~FCUIQtRuntime() = default;

void FCUIQtRuntime::setHost(FCUIQtHost* host) {
    if (host_ == host) {
        return;
    }
    if (host_) {
        disconnect(host_, nullptr, this, nullptr);
    }
    host_ = host;
    if (!host_) {
        return;
    }
    connect(host_, &FCUIQtHost::pathChanged, this, [this](const QString& path, const QVariant& value) {
        hostPaths_.insert(path, value);
        dirtyHost_.insert(path);
        scheduleRefresh();
    });
}

bool FCUIQtRuntime::loadModuleFile(const QString& path, QString* errorMessage) {
    module_ = readJsonObjectFile(path, errorMessage);
    if (module_.isEmpty()) {
        return false;
    }

    componentByName_ = {};
    const auto components = asArray(module_.value("components"));
    for (const auto& c : components) {
        const auto obj = asObject(c);
        const auto name = obj.value("name").toString();
        if (!name.isEmpty()) {
            componentByName_.insert(name, obj);
        }
    }

    if (componentByName_.isEmpty()) {
        if (errorMessage) {
            *errorMessage = "module has no components";
        }
        return false;
    }

    return true;
}

QStringList FCUIQtRuntime::componentNames() const {
    return componentByName_.keys();
}

QVariant FCUIQtRuntime::propValue(const QString& name) const {
    return selfProps_.value(name);
}

void FCUIQtRuntime::setPropValue(const QString& name, const QVariant& value) {
    if (selfProps_.value(name) == value) {
        return;
    }
    selfProps_.insert(name, value);
    dirtySelf_.insert(name);
    scheduleRefresh();
    Q_EMIT propsChanged();
}

QVariant FCUIQtRuntime::hostPathValue(const QString& path) const {
    return hostPaths_.value(path);
}

void FCUIQtRuntime::setHostPathValue(const QString& path, const QVariant& value) {
    if (hostPaths_.value(path) == value) {
        return;
    }
    hostPaths_.insert(path, value);
    dirtyHost_.insert(path);
    scheduleRefresh();
}

void FCUIQtRuntime::flushNow() {
    if (refreshTimer_ && refreshTimer_->isActive()) {
        refreshTimer_->stop();
    }
    flushPendingUpdates();
}

QWidget* FCUIQtRuntime::instantiate(const QString& componentName, QString* errorMessage) {
    bindings_.clear();
    selfProps_.clear();
    hostPaths_.clear();
    dirtySelf_.clear();
    dirtyHost_.clear();

    if (!componentByName_.contains(componentName)) {
        if (errorMessage) {
            *errorMessage = QString("unknown component '%1'").arg(componentName);
        }
        return nullptr;
    }

    activeComponent_ = componentByName_.value(componentName).toObject();

    // Initialize self props from schema defaults (const only in this bootstrap).
    const auto props = asArray(activeComponent_.value("props"));
    for (const auto& p : props) {
        const auto pObj = asObject(p);
        const auto name = pObj.value("name").toString();
        if (name.isEmpty()) {
            continue;
        }

        const auto def = asObject(pObj.value("default"));
        if (def.value("kind").toString() == "const") {
            selfProps_.insert(name, def.value("value").toVariant());
        }
    }

    const auto templateObj = asObject(activeComponent_.value("template"));
    if (templateObj.isEmpty()) {
        if (errorMessage) {
            *errorMessage = "component template missing";
        }
        return nullptr;
    }

    QWidget* root = buildNode(templateObj);
    if (!root) {
        if (errorMessage) {
            *errorMessage = "failed to build widget tree";
        }
        return nullptr;
    }

    primeHostDeps();
    refreshAllBindings();
    return root;
}

QWidget* FCUIQtRuntime::buildNode(const QJsonObject& nodeObj) {
    const auto type = nodeObj.value("type").toString();
    if (type.isEmpty()) {
        return nullptr;
    }

    // Containers first.
    if (type == "Column" || type == "Row" || type == "Group" || type == "Scroll" || type == "Tabs" || type == "Stack" ||
        type == "Splitter" || type == "StatusBar" || type == "Dock" || type == "ToolBar") {
        return buildContainer(type, nodeObj);
    }

    return buildLeaf(type, nodeObj);
}

QWidget* FCUIQtRuntime::buildContainer(const QString& type, const QJsonObject& nodeObj) {
    const auto children = asArray(nodeObj.value("children"));
    const auto props = asObject(nodeObj.value("props"));

    if (type == "Column" || type == "Row") {
        auto* w = new QWidget();
        auto* layout = (type == "Column") ? static_cast<QBoxLayout*>(new QVBoxLayout(w))
                                          : static_cast<QBoxLayout*>(new QHBoxLayout(w));
        layout->setContentsMargins(0, 0, 0, 0);
        layout->setSpacing(6);
        for (const auto& child : children) {
            QWidget* cw = buildNode(asObject(child));
            if (cw) {
                layout->addWidget(cw);
            }
        }
        return w;
    }

    if (type == "Group") {
        auto* g = new QGroupBox();
        // text prop maps to group title
        if (props.contains("text")) {
            addPropBinding(g, type, "text", asObject(props.value("text")));
        }
        auto* inner = new QWidget();
        auto* layout = new QVBoxLayout(inner);
        layout->setContentsMargins(6, 6, 6, 6);
        layout->setSpacing(6);
        for (const auto& child : children) {
            QWidget* cw = buildNode(asObject(child));
            if (cw) {
                layout->addWidget(cw);
            }
        }
        auto* gLayout = new QVBoxLayout(g);
        gLayout->setContentsMargins(0, 0, 0, 0);
        gLayout->addWidget(inner);
        return g;
    }

    if (type == "Scroll") {
        auto* scroll = new QScrollArea();
        scroll->setWidgetResizable(true);
        if (!children.isEmpty()) {
            QWidget* cw = buildNode(asObject(children.first()));
            if (cw) {
                scroll->setWidget(cw);
            }
        }
        return scroll;
    }

    if (type == "Tabs") {
        auto* tabs = new QTabWidget();
        int idx = 1;
        for (const auto& child : children) {
            QWidget* cw = buildNode(asObject(child));
            if (cw) {
                tabs->addTab(cw, QString("Tab %1").arg(idx++));
            }
        }
        return tabs;
    }

    if (type == "Stack") {
        // Simplified as QTabWidget without tabs (placeholder).
        auto* stack = new QTabWidget();
        stack->tabBar()->hide();
        for (const auto& child : children) {
            QWidget* cw = buildNode(asObject(child));
            if (cw) {
                stack->addTab(cw, QString());
            }
        }
        return stack;
    }

    if (type == "Splitter") {
        auto* splitter = new QSplitter();
        splitter->setChildrenCollapsible(false);

        if (props.contains("orientation")) {
            const QString o = evalValue(asObject(props.value("orientation"))).toString().toLower();
            splitter->setOrientation(o == "vertical" ? Qt::Vertical : Qt::Horizontal);
        } else {
            splitter->setOrientation(Qt::Horizontal);
        }

        int idx = 0;
        for (const auto& child : children) {
            QWidget* cw = buildNode(asObject(child));
            if (!cw) {
                continue;
            }
            splitter->addWidget(cw);
            splitter->setStretchFactor(idx, 1);
            idx++;
        }
        return splitter;
    }

    if (type == "StatusBar") {
        auto* bar = new QStatusBar();
        bar->setSizeGripEnabled(false);

        bool permanent = false;
        for (const auto& child : children) {
            const auto childObj = asObject(child);
            const auto childType = childObj.value("type").toString();
            if (childType == "Spacer") {
                permanent = true;
                continue;
            }
            QWidget* cw = buildNode(childObj);
            if (!cw) {
                continue;
            }
            if (permanent) {
                bar->addPermanentWidget(cw);
            } else {
                bar->addWidget(cw);
            }
        }
        return bar;
    }

    if (type == "Dock") {
        // Render as a plain QWidget wrapper tagged with dock metadata; the app shell can "promote" it to QDockWidget.
        auto* dockRoot = new QWidget();
        dockRoot->setContentsMargins(0, 0, 0, 0);
        auto* layout = new QVBoxLayout(dockRoot);
        layout->setContentsMargins(0, 0, 0, 0);
        layout->setSpacing(0);

        if (!children.isEmpty()) {
            QWidget* cw = buildNode(asObject(children.first()));
            if (cw) {
                layout->addWidget(cw);
            }
        }

        QString area = "left";
        if (props.contains("area")) {
            area = evalValue(asObject(props.value("area"))).toString();
        }
        QString title = "Dock";
        if (props.contains("title")) {
            title = evalValue(asObject(props.value("title"))).toString();
        }
        QVariant sizeV;
        if (props.contains("size")) {
            sizeV = evalValue(asObject(props.value("size")));
        }

        dockRoot->setProperty("fcui.dock.area", area);
        dockRoot->setProperty("fcui.dock.title", title);
        if (sizeV.isValid()) {
            dockRoot->setProperty("fcui.dock.size", sizeV);
        }
        return dockRoot;
    }

    if (type == "ToolBar") {
        // Render as a plain QWidget wrapper tagged with toolbar metadata; the app shell can "promote" it to QToolBar.
        auto* tbRoot = new QWidget();
        tbRoot->setContentsMargins(0, 0, 0, 0);
        auto* layout = new QHBoxLayout(tbRoot);
        layout->setContentsMargins(0, 0, 0, 0);
        layout->setSpacing(4);

        for (const auto& child : children) {
            QWidget* cw = buildNode(asObject(child));
            if (cw) {
                layout->addWidget(cw);
            }
        }

        QString area = "top";
        if (props.contains("area")) {
            area = evalValue(asObject(props.value("area"))).toString();
        }
        QString title = "Toolbar";
        if (props.contains("title")) {
            title = evalValue(asObject(props.value("title"))).toString();
        }

        tbRoot->setProperty("fcui.toolbar.area", area);
        tbRoot->setProperty("fcui.toolbar.title", title);
        return tbRoot;
    }

    // Fallback container.
    auto* fallback = new QWidget();
    auto* layout = new QVBoxLayout(fallback);
    layout->setContentsMargins(0, 0, 0, 0);
    for (const auto& child : children) {
        QWidget* cw = buildNode(asObject(child));
        if (cw) {
            layout->addWidget(cw);
        }
    }
    return fallback;
}

QWidget* FCUIQtRuntime::buildLeaf(const QString& type, const QJsonObject& nodeObj) {
    const auto props = asObject(nodeObj.value("props"));

    if (type == "Text") {
        auto* label = new QLabel();
        label->setTextInteractionFlags(Qt::TextSelectableByMouse);
        if (props.contains("text")) {
            addPropBinding(label, type, "text", asObject(props.value("text")));
        }
        return label;
    }

    if (type == "Button") {
        auto* btn = new QPushButton();
        if (props.contains("text")) {
            addPropBinding(btn, type, "text", asObject(props.value("text")));
        }
        if (props.contains("enabled")) {
            addPropBinding(btn, type, "enabled", asObject(props.value("enabled")));
        }
        if (props.contains("clicked")) {
            const auto v = asObject(props.value("clicked"));
            const auto kind = v.value("kind").toString();
            if (kind == "command") {
                const auto cmd = v.value("name").toString();
                connect(btn, &QPushButton::clicked, this, [this, cmd]() {
                    if (host_) {
                        host_->invokeCommand(cmd, {});
                    }
                });
            }
        }
        return btn;
    }

    if (type == "Toggle") {
        auto* cb = new QCheckBox();
        if (props.contains("text")) {
            addPropBinding(cb, type, "text", asObject(props.value("text")));
        }
        if (props.contains("enabled")) {
            addPropBinding(cb, type, "enabled", asObject(props.value("enabled")));
        }
        return cb;
    }

    if (type == "TextInput") {
        auto* le = new QLineEdit();
        if (props.contains("enabled")) {
            addPropBinding(le, type, "enabled", asObject(props.value("enabled")));
        }
        return le;
    }

    if (type == "NumberInput") {
        auto* spin = new QSpinBox();
        spin->setRange(std::numeric_limits<int>::min(), std::numeric_limits<int>::max());
        if (props.contains("enabled")) {
            addPropBinding(spin, type, "enabled", asObject(props.value("enabled")));
        }
        return spin;
    }

    if (type == "Separator") {
        auto* f = new QFrame();
        f->setFrameShape(QFrame::HLine);
        f->setFrameShadow(QFrame::Sunken);
        return f;
    }

    if (type == "Spacer") {
        auto* w = new QWidget();
        w->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Preferred);
        w->setMinimumSize(0, 0);
        return w;
    }

    if (type == "NativeWidget") {
        QVariantMap p;
        for (auto it = props.begin(); it != props.end(); ++it) {
            p.insert(it.key(), evalValue(asObject(it.value())));
        }

        QString kind = p.value("kind").toString();
        if (kind.isEmpty()) {
            kind = p.value("class_name").toString();
        }
        if (kind.isEmpty()) {
            kind = "NativeWidget";
        }

        if (host_) {
            if (QWidget* w = host_->createNativeWidget(kind, p, nullptr)) {
                return w;
            }
        }

        auto* label = new QLabel(QString("NativeWidget(%1) unavailable").arg(kind));
        label->setStyleSheet("color: #a00;");
        return label;
    }

    auto* label = new QLabel(QString("Unsupported node: %1").arg(type));
    label->setStyleSheet("color: #a00;");
    return label;
}

void FCUIQtRuntime::addPropBinding(
    QWidget* widget,
    const QString& nodeType,
    const QString& propName,
    const QJsonObject& valueObj
) {
    const auto kind = valueObj.value("kind").toString();

    auto setProp = [widget, nodeType, propName](const QVariant& v) {
        if (nodeType == "Text" && propName == "text") {
            auto* label = qobject_cast<QLabel*>(widget);
            if (label) {
                label->setText(v.toString());
            }
            return;
        }
        if (nodeType == "Button" && propName == "text") {
            auto* btn = qobject_cast<QPushButton*>(widget);
            if (btn) {
                btn->setText(v.toString());
            }
            return;
        }
        if (nodeType == "Button" && propName == "enabled") {
            widget->setEnabled(v.toBool());
            return;
        }
        if (nodeType == "Toggle" && propName == "text") {
            auto* cb = qobject_cast<QCheckBox*>(widget);
            if (cb) {
                cb->setText(v.toString());
            }
            return;
        }
        if (propName == "enabled") {
            widget->setEnabled(v.toBool());
            return;
        }
        if (nodeType == "Group" && propName == "text") {
            auto* gb = qobject_cast<QGroupBox*>(widget);
            if (gb) {
                gb->setTitle(v.toString());
            }
            return;
        }
    };

    if (kind == "const") {
        setProp(valueObj.value("value").toVariant());
        return;
    }

    if (kind == "host_path") {
        FcuiBinding b;
        b.source = valueObj.value("source").toString();
        const auto path = valueObj.value("path").toString();
        if (!path.isEmpty()) {
            b.hostDeps.insert(path);
        }
        b.apply = [this, valueObj, setProp]() { setProp(evalValue(valueObj)); };
        bindings_.push_back(std::move(b));
        return;
    }

    if (kind == "vm") {
        FcuiBinding b;
        b.source = valueObj.value("source").toString();
        const auto ops = asArray(valueObj.value("ops"));
        const auto deps = depsFromOps(ops);
        b.selfDeps = deps.selfDeps;
        b.hostDeps = deps.hostDeps;
        b.apply = [this, valueObj, setProp]() { setProp(evalValue(valueObj)); };
        bindings_.push_back(std::move(b));
        return;
    }

    // Other kinds (host_path/command) are not props in this viewer.
}

QVariant FCUIQtRuntime::evalValue(const QJsonObject& valueObj) const {
    const auto kind = valueObj.value("kind").toString();
    if (kind == "const") {
        return valueObj.value("value").toVariant();
    }
    if (kind == "host_path") {
        const auto path = valueObj.value("path").toString();
        if (hostPaths_.contains(path)) {
            return hostPaths_.value(path);
        }
        if (host_) {
            return host_->readPath(path);
        }
        return {};
    }
    if (kind == "vm") {
        const auto ops = asArray(valueObj.value("ops"));
        return vm_->eval(ops, selfProps_, hostPaths_);
    }
    return {};
}

void FCUIQtRuntime::refreshAllBindings() {
    for (const auto& b : bindings_) {
        if (b.apply) {
            b.apply();
        }
    }
}

void FCUIQtRuntime::refreshBindingsForSelf(const QString& propName) {
    for (const auto& b : bindings_) {
        if (!b.apply) {
            continue;
        }
        if (b.selfDeps.contains(propName)) {
            b.apply();
        }
    }
}

void FCUIQtRuntime::refreshBindingsForHostPath(const QString& path) {
    for (const auto& b : bindings_) {
        if (!b.apply) {
            continue;
        }
        if (b.hostDeps.contains(path)) {
            b.apply();
        }
    }
}

void FCUIQtRuntime::scheduleRefresh() {
    if (!refreshTimer_) {
        flushPendingUpdates();
        return;
    }
    if (!refreshTimer_->isActive()) {
        refreshTimer_->start();
    }
}

void FCUIQtRuntime::flushPendingUpdates() {
    if (dirtySelf_.isEmpty() && dirtyHost_.isEmpty()) {
        return;
    }

    const auto dirtySelf = dirtySelf_;
    const auto dirtyHost = dirtyHost_;
    dirtySelf_.clear();
    dirtyHost_.clear();

    for (const auto& b : bindings_) {
        if (!b.apply) {
            continue;
        }
        bool hit = false;
        for (const auto& k : dirtySelf) {
            if (b.selfDeps.contains(k)) {
                hit = true;
                break;
            }
        }
        if (!hit) {
            for (const auto& k : dirtyHost) {
                if (b.hostDeps.contains(k)) {
                    hit = true;
                    break;
                }
            }
        }
        if (hit) {
            b.apply();
        }
    }
}

void FCUIQtRuntime::primeHostDeps() {
    if (!host_) {
        return;
    }
    QSet<QString> deps;
    for (const auto& b : bindings_) {
        deps.unite(b.hostDeps);
    }
    for (const auto& p : deps) {
        hostPaths_.insert(p, host_->readPath(p));
    }
}
