// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <algorithm>

#include <App/Application.h>
#include <Base/Parameter.h>

namespace Gui
{

enum class WorkbenchContextPolicy
{
    Global = 0,
    Document = 1,
    View = 2,
};

inline constexpr WorkbenchContextPolicy DefaultWorkbenchContextPolicy = WorkbenchContextPolicy::View;

inline ParameterGrp::handle workbenchContextPolicyParameters()
{
    return App::GetApplication().GetParameterGroupByPath("User parameter:BaseApp/Preferences/View");
}

inline bool hasWorkbenchContextPolicyParameter(
    const ParameterGrp::handle& hGrp,
    ParameterGrp::ParamType type,
    const char* name
)
{
    const auto params = hGrp->GetParameterNames(name);
    return std::any_of(params.begin(), params.end(), [type, name](const auto& param) {
        return param.first == type && param.second == name;
    });
}

inline WorkbenchContextPolicy getWorkbenchContextPolicy()
{
    const auto hGrp = workbenchContextPolicyParameters();
    if (
        hasWorkbenchContextPolicyParameter(hGrp, ParameterGrp::ParamType::FCInt, "WorkbenchContextPolicy")
    ) {
        const long policy = hGrp->GetInt(
            "WorkbenchContextPolicy",
            static_cast<long>(DefaultWorkbenchContextPolicy)
        );
        if (policy >= static_cast<long>(WorkbenchContextPolicy::Global)
            && policy <= static_cast<long>(WorkbenchContextPolicy::View)) {
            return static_cast<WorkbenchContextPolicy>(policy);
        }
    }

    if (hasWorkbenchContextPolicyParameter(hGrp, ParameterGrp::ParamType::FCBool, "SaveWBbyTab")) {
        return hGrp->GetBool("SaveWBbyTab", false) ? WorkbenchContextPolicy::View
                                                   : WorkbenchContextPolicy::Document;
    }

    return DefaultWorkbenchContextPolicy;
}

inline void setWorkbenchContextPolicy(WorkbenchContextPolicy policy)
{
    const auto hGrp = workbenchContextPolicyParameters();
    hGrp->SetInt("WorkbenchContextPolicy", static_cast<long>(policy));
    hGrp->SetBool("SaveWBbyTab", policy == WorkbenchContextPolicy::View);
}

inline void resetWorkbenchContextPolicy()
{
    const auto hGrp = workbenchContextPolicyParameters();
    hGrp->RemoveInt("WorkbenchContextPolicy");
    hGrp->RemoveBool("SaveWBbyTab");
}

}  // namespace Gui
