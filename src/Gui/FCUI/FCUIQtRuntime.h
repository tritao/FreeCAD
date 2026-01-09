#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QSet>
#include <QTimer>
#include <QVariant>
#include <QVector>
#include <QWidget>

#include <functional>
#include <memory>

class VmEval;

struct FcuiBinding {
    QString source;
    QSet<QString> selfDeps;
    QSet<QString> hostDeps;
    std::function<void()> apply;
};

class FCUIQtHost;

class FCUIQtRuntime final : public QObject {
    Q_OBJECT

public:
    explicit FCUIQtRuntime(FCUIQtHost* host = nullptr, QObject* parent = nullptr);
    ~FCUIQtRuntime() override;

    bool loadModuleFile(const QString& path, QString* errorMessage);
    QStringList componentNames() const;
    QWidget* instantiate(const QString& componentName, QString* errorMessage);

    QVariant propValue(const QString& name) const;
    void setPropValue(const QString& name, const QVariant& value);

    QVariant hostPathValue(const QString& path) const;
    void setHostPathValue(const QString& path, const QVariant& value);

    void flushNow();

    void setHost(FCUIQtHost* host);

Q_SIGNALS:
    void propsChanged();

private:
    QWidget* buildNode(const QJsonObject& nodeObj);
    QWidget* buildContainer(const QString& type, const QJsonObject& nodeObj);
    QWidget* buildLeaf(const QString& type, const QJsonObject& nodeObj);

    void addPropBinding(
        QWidget* widget,
        const QString& nodeType,
        const QString& propName,
        const QJsonObject& valueObj
    );

    QVariant evalValue(const QJsonObject& valueObj) const;
    void refreshAllBindings();
    void refreshBindingsForSelf(const QString& propName);
    void refreshBindingsForHostPath(const QString& path);

    void scheduleRefresh();
    void flushPendingUpdates();
    void primeHostDeps();

    QJsonObject module_;
    QJsonObject componentByName_;
    QJsonObject activeComponent_;

    QVariantMap selfProps_;
    QVariantMap hostPaths_;

    QVector<FcuiBinding> bindings_;
    std::unique_ptr<VmEval> vm_;

    QSet<QString> dirtySelf_;
    QSet<QString> dirtyHost_;
    QTimer* refreshTimer_ = nullptr;

    FCUIQtHost* host_ = nullptr;
};
