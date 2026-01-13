// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 The FreeCAD project association AISBL
// SPDX-FileNotice: Part of the FreeCAD project.
/******************************************************************************
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

#pragma once

#include <type_traits>
#include <utility>

namespace Base
{

template<typename Fn>
class ScopeExit
{
public:
    explicit ScopeExit(Fn&& function)
        : function_(std::forward<Fn>(function))
    {}

    ScopeExit(const ScopeExit&) = delete;
    ScopeExit& operator=(const ScopeExit&) = delete;

    ScopeExit(ScopeExit&& other) noexcept(std::is_nothrow_move_constructible_v<Fn>)
        : function_(std::move(other.function_))
        , active_(other.active_)
    {
        other.active_ = false;
    }

    ScopeExit& operator=(ScopeExit&& other) noexcept(std::is_nothrow_move_assignable_v<Fn>)
    {
        if (this != &other) {
            if (active_) {
                function_();
            }
            function_ = std::move(other.function_);
            active_ = other.active_;
            other.active_ = false;
        }
        return *this;
    }

    ~ScopeExit()
    {
        if (active_) {
            function_();
        }
    }

    void release() noexcept
    {
        active_ = false;
    }

private:
    Fn function_;
    bool active_ {true};
};

template<typename Fn>
auto makeScopeExit(Fn&& function)
{
    return ScopeExit<std::decay_t<Fn>>(std::forward<Fn>(function));
}

}  // namespace Base
