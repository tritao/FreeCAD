#pragma once

#include <QObject>
#include <QVariant>
#include <QVariantMap>

class QWidget;

class FCUIQtHost : public QObject {
    Q_OBJECT

public:
    using QObject::QObject;
    ~FCUIQtHost() override = default;

    virtual QVariant readPath(const QString& path) const = 0;
    virtual QWidget* createNativeWidget(const QString& kind, const QVariantMap& props, QWidget* parent) = 0;

public Q_SLOTS:
    virtual void invokeCommand(const QString& name, const QVariantList& args) = 0;

Q_SIGNALS:
    void pathChanged(const QString& path, const QVariant& value);
};
