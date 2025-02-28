

RFC: Improved FreeCAD dependency management
================================================

Currently there are some challenges around adding and vendoring dependencies in FreeCAD,
as well as the management of existing dependencies. We would like to vendor dependencies
such as Coin, but this requires a careful analysis of the best way to do it.

This is meant as an overview for how the existing dependency and build management system works,
an analysis of the tradeoffs between different approaches, as well as potential solutions.

With the end goal of reaching an informed decision that realizes all the requirements of the
project, and discussed between all stakeholders of the FreeCAD community.

## Dependencies Build Management

When it comes to build management of dependencies, we have two possible approaches.

1. **Compile from source**

2. **Retrieve pre-compiled binaries**

At the moment, FreeCAD's infrastructure is mostly is catered towards 2., which provides a good
set of benefits, namely much faster compilation for both users and CI, but **there are certain
use cases where compiling everything from source is a necessity**:

1. **Supporting novel platforms for which there are no binary dependencies**

    For example, for supporting a new platform like the web via Emscripten, all dependencies need to be
    compiled from source, since there are no pre-packaged builds.

2. **Supporting non-default build flags**

    Sometimes the project needs to be compiled with different set of non-default build flags, for
    use cases such as profiling, debugging and advanced instrumentation like ASAN/MSAN/TSAN memory/thread sanitizers.

    Another recent use case that I am facing, I'd like to debug using the LLDB debugger on Linux, which
    provides better debugging in some situations. But this involves compiling FreeCAD and all its
    dependencies using libc++ standard library, which is currently not possible to do out of the box.

    Binary dependencies are pre-compiled and thus they are produced for a given static build configuration, as such
    they are not suitable.

3. **Supporting custom dependency versions**

    Pre-packaged dependencies, due to their nature, are quite often out-of-date as soon as they are published,
    as its not feasible to prepackage versions for all new published code for all dependencies. As such, to be
    able to test FreeCAD with upstream code as its released, or for hot fixes, a build from source is necessary.

Overall both approaches are not in conflict with each other, and in practice a pragmatic mix of both approaches
is often required for a single build.

They both should be supported by a project with such scale as FreeCAD.

## Dependency Source Management

When it comes to managing dependencies, there are certain approaches typically used:

1. **Including the source code in the repository**

    In this approach, the source files for the dependency are directly embedded into the host
    repository. This is currently done in FreeCAD for some dependencies, for example, some of 
    the entries in the `src/3rdParty` folder, such as `libE57Format`, `libkdtree` and `salomesmesh`.

    This can lead to some problems, as it makes it much more troublesome to keep up-to-sync
    with upstream, and to easily check what custom changes have been done. 

    The general consensus seems to be that this method should be discouraged and
    existing uses be ported to be external modules, as explained in approach 2. below.

2. **Referencing them as external modules**

    In this approach, source code for the dependency is kept in a separate Git repository, which
    can be hosted and controlled by the FreeCAD organization itself, or be controlled by a third-party,
    and just referenced by the project.

    There are different available approaches to referencing them:

    * either to use Git external code referencing features directly,
    * use a dedicated dependency management tool (which calls back to Git usually)

    Next we analyze these in more detail.

    #### a. Git Submodules

    Git submodules let you reference external repositories at specific commits inside your main repository.
    * **Pros:**
        * Provides clear boundaries between your code and external code.
        * You can lock dependencies to a specific commit or version.
        * 
    * **Cons:**
        * Users must remember to initialize and update submodules after cloning.
        * Merging changes (both upstream and local) can be tricky.
        * No easy to way to specify which submodules should be cloned
        * Forces everyone to pay the cost of cloning dependencies as there's no practical selectiveness mechanism

    #### b. Git Subtree

    Git subtree allows you to merge an external repository into a subdirectory of your main repository.
    It preserves the history of the external dependency while making it part of your repository.
    * **Pros:**
        * No extra commands are required after cloning (unlike submodules).
        * Merges updates from upstream are possible though the process is more manual and needs subtree specific
        commands.
    * **Cons:**
        * Leads to a larger host repository due to the additional history.
        * Updating the subtree is less straightforward compared to submodules.
        * Forces everyone to pay the cost of cloning dependencies as there's no selectiveness mechanism

    #### c. CMake FetchContent

    FetchContent allows you to declare the dependency versions and revisions in CMake scripts.
    CMake then sets up (downloads) and includes dependencies during the CMake configuration step.

    * **Pros:**
        * Can simplify dependency management by fetching the required code at configure time.
        * Easily integrates with the CMake build process.
        * No extra dependency is needed
    * **Cons:**
        * May increase configuration time.
        * Dependency versions must be carefully managed.
        * CMake scripting language is not the most user friendly

    #### d. West

    West is a Python meta-tool primarily designed for managing multiple Git repositories.
    It allows management of dependencies across several repositories by defining a manifest file 
    that lists all the required projects and their respective revisions.

    * **Pros:**
        * Centralized Dependency Management: Uses a single manifest file to specify versions and sources for all
        dependencies.
        * Ensures that all parts of the project use compatible versions, as the manifest locks each dependency to
        a specific commit.
        * Automates the process of cloning, updating, and managing multiple repositories.
        * Since it's an YAML format, it can be easily extended with custom metadata
    * **Cons:**
        * Requires familiarity with the West tool and its manifest configuration.
        * Project become dependent on West; users must install and use it to manage dependencies.





## Build Configurations

Now lets look at the way FreeCAD is currently built.
These are the main build configurations supported by either FreeCAD or its community:

1. **Pure CMake builds**

    This is the default when doing a pure CMake build, will search for dependencies
    in the system locations, as probed by CMake, and errors if they are not found.

    Some bundled dependencies are still built from source, as required by FreeCAD.

    For building in Linux distros, this build type works pretty well and can be the preferred option,
    as it will allow use of distro provided dependencies.

2. **Pixi-based builds**

    [Pixi](https://pixi.sh/) is a package management tool for developers.
    This build grabs all dependencies as binaries from Conda feeds and sets up the build with `CMakePresets.json`.

    Some bundled dependencies are still built from source, as required by FreeCAD.

    This build type is very nice to use as it takes care of fetching all available prepacked dependencies,
    thus making the build process quite a lot faster, and should be the preferred default option for new users.

3. **LibPack-based builds**

    This build type fetches all pre-packaged dependencies from an archive. This archive was previously build,
    and contains pre-packaged dependencies which are built from source using a Python-based
    build script infrastructure, maintained by @chennes. 

    This system is used for Windows CI builds (and official releases right now?).

4. **Distro-specific builds**

    There are scripts for building FreeCAD for specific distros, which are maintained either in the repo or externally.

    Fedora uses `package/fedora/freecad.spec` to setup distro-specific packages which are used by the build later
    (as in 1.).

    Debian uses separately maintained build scripts at: https://salsa.debian.org/science-team/freecad
    Which are also the recipe for the PPA: https://code.launchpad.net/~freecad-maintainers/freecad/+git/freecad-salsa

5. **CI builds**

    1. Pixi builds (Linux, Windows and macOS)

        These use the Pixi system (`pixi.toml`) described earlier to manage most of their dependencies.

    2. Ubuntu (22.04)

        Manual setup of the dependencies using an hardcoded [list of Apt packages](https://github.com/FreeCAD/FreeCAD/blob/main/.github/workflows/sub_buildUbuntu.yml#L81)

    3. Windows (LibPack)

        Dependencies are managed using [getLibPack CI action](https://github.com/FreeCAD/FreeCAD/blob/main/.github/workflows/actions/windows/getLibpack/action.yml)

        Version is static and [hardcoded in CI file](https://github.com/FreeCAD/FreeCAD/blob/main/.github/workflows/actions/windows/getLibpack/action.yml#L44) as a variable:

        ```default: https://.../FreeCAD-LibPack/.../LibPack-1.0.0-v3.0.0RC4-Release.7z```


A solution to the dependency management problem should take into account the needs of all the build variants.

## Current Approach

FreeCAD at the moment uses a mix of both `Git Submodule` and `FetchContent` approaches for managing source dependencies.

Additionally LibPack provides its own way of declaring source dependencies in the form of a [`config.json`](https://github.com/FreeCAD/FreeCAD-LibPack/blob/main/config.json
), which is another instance of the same underlying problem. This approach is not ideal as dependencies can easily
get out of sync. Instead the dependencies should be specified by the main FreeCAD repository itself, 
so they can updated atomically via Git at the same time as the code that uses such dependencies.

This mix of systems is not ideal as this means **dependencies are scattered around multiple different systems**.


### Git Submodule Dependencies

| **Submodule Name** | **Path** | **URL** |
| --- | --- | --- |
| OndselSolver | src/3rdParty/OndselSolver | [https://github.com/Ondsel-Development/OndselSolver.git](https://github.com/Ondsel-Development/OndselSolver.git) |
| googletest | tests/lib | [https://github.com/google/googletest](https://github.com/google/googletest) |
| GSL | src/3rdParty/GSL | [https://github.com/microsoft/GSL](https://github.com/microsoft/GSL) |


### FetchContent-Based Dependencies

| **Dependency** | **Path** | **URL** |
| --- | --- | --- |
| fmt | FreeCAD/cMake/FreeCAD_Helpers/SetupLibFmt.cmake| [https://github.com/fmtlib/fmt/archive/refs/tags/9.1.0.zip](https://github.com/fmtlib/fmt/archive/refs/tags/9.1.0.zip) |
* * *




## Requirements

Lets define some of the requirements a solution should fulfill.

1. Single system

Whatever system is used, it should be used for _all_ dependencies.
This simplifies the overall system and means its easier to learn and use for new developers.

2. 



1. Binary package managers

In the case of binary-based package managers, like Pixi, which already tracks its own dependencies, then
**its own way of tracking existing dependencies should be preferred and continue to be used**.

But **for dependencies which do not exist as binary packages**, then FreeCAD's own dependency managing system would
take into action and do the necessary setup to download the external sources, or other kind of artifacts,
before the Pixi-based CMake build process begins.

And it should be possible at build-time to override a dependency with the one specified by Free


1. Binary package managers

There should be a unified system for managing dependencies, **where possible**, both for from-source builds,
as well as for prepackaged builds.



## Solutions

There is a recent [proposal/PR](https://github.com/FreeCAD/FreeCAD/pull/19276) by @oursland to migrate an existing
dependency to `Git Subtree` system.

This effort is much appreciated as FreeCAD definitely needs a solution to the problem, but should be carefully
analyzed, so FreeCAD can make a good conscious decision of an overall approach that fully matches the need for all
use cases of the project.

https://github.com/FreeCAD/FreeCAD/pull/19276#issuecomment-2615141263




There are two major benefits that arise from this strategy:

Single repo for the source

A single clone of the source tree brings in all of the code necessary to build without having to connect to remote
repositories.

Branch switches and merges are simplified

The use of git submodules have a consequence of changing branches that the submodules may need to be updated, which
is a process that is not automatic. Merges in which multiple changes in submodules is also extremely difficult.

With git subtree, branch changes and merges are no different than any other code. There are no additional steps
necessary.










----



> The build system for the official releases already has dependency management.  The pixi system in the FreeCAD tree contains lock files, so it produces reproducible builds.  This will be brought to the freecad-feedstock eventually.

This dependency management is only done for Pixi and only usable for prepackaged dependencies.
Its not unified with the rest of the build approaches and cannot be used for source-based vendored dependencies.

Even with Pixi build, there needs to be a dependency management system for FreeCAD specific vendored dependencies.

> Building unmodified dependencies from source is not a wise idea for FreeCAD.  Our CI system depends upon using ccache that is retained.  We only have a 10 GiB allowance for such cache artifacts and a full rebuild takes up something like half that as is.  If we were to add unmodified dependencies, we'd exceed the cache sizes making all CI builds take considerably longer with no discernable gain.

I don't agree with this take that it's "unwise" to build unmodified dependencies from source.
The CI point makes sense, but it's not relevant to the discussion as the CI can just keep using the same system.

> It makes sense that these components are included, preferably via git subtree, as it eliminates the network dependency for updates and simplifies the challenges posed by managing and synchronizing commits among multiple repositories.

I don't think the network dependency angle here holds much weight as the rest of the build already depends on network to get components (be it either Pixi, or FetchContent as is used today, or even Git submodules, like OndselSolver).

As for the challenges of synchronizing commits among multiple repositories, I am not really sure what you mean. Maybe you can explain in more detail.
