// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2026                                                   *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/

#include "FileLock.h"

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <thread>

#if defined(__EMSCRIPTEN__)

using namespace Base;

FileLock::FileLock(std::string path)
    : _path(std::move(path))
{}

FileLock::~FileLock() = default;

bool FileLock::tryLock(int /*timeoutMs*/)
{
    _locked = true;
    return true;
}

bool FileLock::lock()
{
    _locked = true;
    return true;
}

void FileLock::unlock()
{
    _locked = false;
}

bool FileLock::isLocked() const
{
    return _locked;
}

#elif defined(_WIN32)

#include <windows.h>

using namespace Base;

namespace
{
constexpr std::chrono::milliseconds pollInterval {10};

bool tryLockHandle(HANDLE handle)
{
    OVERLAPPED ov {};
    const BOOL ok = LockFileEx(
        handle,
        LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY,
        0,
        MAXDWORD,
        MAXDWORD,
        &ov
    );
    return ok != 0;
}

void unlockHandle(HANDLE handle)
{
    OVERLAPPED ov {};
    UnlockFileEx(handle, 0, MAXDWORD, MAXDWORD, &ov);
}
}  // namespace

FileLock::FileLock(std::string path)
    : _path(std::move(path))
{
    _handle = INVALID_HANDLE_VALUE;
}

FileLock::~FileLock()
{
    unlock();
}

bool FileLock::tryLock(int timeoutMs)
{
    if (_locked) {
        return true;
    }

    const std::filesystem::path p = std::filesystem::u8path(_path);
    const std::wstring wpath = p.wstring();

    HANDLE handle = CreateFileW(
        wpath.c_str(),
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr
    );
    if (handle == INVALID_HANDLE_VALUE) {
        return false;
    }

    const auto deadline = (timeoutMs < 0)
        ? std::chrono::steady_clock::time_point::max()
        : (std::chrono::steady_clock::now() + std::chrono::milliseconds(timeoutMs));

    while (std::chrono::steady_clock::now() <= deadline) {
        if (tryLockHandle(handle)) {
            _handle = handle;
            _locked = true;
            return true;
        }

        const DWORD err = GetLastError();
        if (err != ERROR_LOCK_VIOLATION) {
            CloseHandle(handle);
            return false;
        }

        if (deadline == std::chrono::steady_clock::time_point::max()) {
            std::this_thread::sleep_for(pollInterval);
        }
        else {
            const auto remaining = deadline - std::chrono::steady_clock::now();
            if (remaining <= std::chrono::milliseconds::zero()) {
                break;
            }
            std::this_thread::sleep_for(std::min(pollInterval, std::chrono::duration_cast<std::chrono::milliseconds>(remaining)));
        }
    }

    CloseHandle(handle);
    return false;
}

bool FileLock::lock()
{
    return tryLock(-1);
}

void FileLock::unlock()
{
    if (!_locked) {
        return;
    }
    auto handle = static_cast<HANDLE>(_handle);
    if (handle != INVALID_HANDLE_VALUE) {
        unlockHandle(handle);
        CloseHandle(handle);
    }
    _handle = INVALID_HANDLE_VALUE;
    _locked = false;
}

bool FileLock::isLocked() const
{
    return _locked;
}

#else

#include <cerrno>
#include <cstring>

#include <fcntl.h>
#include <unistd.h>

using namespace Base;

namespace
{
constexpr std::chrono::milliseconds pollInterval {10};

bool tryLockFd(int fd)
{
    struct flock fl {};
    fl.l_type = F_WRLCK;
    fl.l_whence = SEEK_SET;
    fl.l_start = 0;
    fl.l_len = 0;  // whole file
    return ::fcntl(fd, F_SETLK, &fl) == 0;
}

void unlockFd(int fd)
{
    struct flock fl {};
    fl.l_type = F_UNLCK;
    fl.l_whence = SEEK_SET;
    fl.l_start = 0;
    fl.l_len = 0;
    (void)::fcntl(fd, F_SETLK, &fl);
}
}  // namespace

FileLock::FileLock(std::string path)
    : _path(std::move(path))
{}

FileLock::~FileLock()
{
    unlock();
}

bool FileLock::tryLock(int timeoutMs)
{
    if (_locked) {
        return true;
    }

    const int fd = ::open(_path.c_str(), O_RDWR | O_CREAT, 0666);
    if (fd < 0) {
        return false;
    }

    const auto deadline = (timeoutMs < 0)
        ? std::chrono::steady_clock::time_point::max()
        : (std::chrono::steady_clock::now() + std::chrono::milliseconds(timeoutMs));

    while (std::chrono::steady_clock::now() <= deadline) {
        if (tryLockFd(fd)) {
            _fd = fd;
            _locked = true;
            return true;
        }

        if (errno != EACCES && errno != EAGAIN) {
            ::close(fd);
            return false;
        }

        if (deadline == std::chrono::steady_clock::time_point::max()) {
            std::this_thread::sleep_for(pollInterval);
        }
        else {
            const auto remaining = deadline - std::chrono::steady_clock::now();
            if (remaining <= std::chrono::milliseconds::zero()) {
                break;
            }
            std::this_thread::sleep_for(std::min(pollInterval, std::chrono::duration_cast<std::chrono::milliseconds>(remaining)));
        }
    }

    ::close(fd);
    return false;
}

bool FileLock::lock()
{
    return tryLock(-1);
}

void FileLock::unlock()
{
    if (!_locked) {
        return;
    }

    unlockFd(_fd);
    ::close(_fd);
    _fd = -1;
    _locked = false;
}

bool FileLock::isLocked() const
{
    return _locked;
}

#endif
