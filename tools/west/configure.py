'''configure.py

West command extension for FreeCAD.'''

from os import path, chmod
from textwrap import dedent
from shutil import copyfile
from stat import S_IREAD, S_IRGRP, S_IROTH, S_IWUSR

from west.commands import WestCommand
from west.manifest import Manifest
from west.util import west_topdir

class ConfigureCommand(WestCommand):

    def __init__(self):
        super().__init__(
            'configure',
            'configure the third-party projects for building',
            # self.description:
            dedent('''
            Configures third-party projects by copying the Justfile build scripts.
            '''))

    def do_add_parser(self, parser_adder):
        parser = parser_adder.add_parser(self.name,
                                         help=self.help,
                                         description=self.description)
        return parser

    def do_run(self, args, unknown_args):
        topdir = west_topdir()
        tools_build = path.join(topdir, "tools", "build")
        manifest = Manifest.from_topdir()
        for project in manifest.projects[1:]:
            if project.name in ["emsdk"]:
                continue
            justfile =  "Justfile.{}".format(project.name)
            justfile_path = path.join(tools_build,justfile)
            if not path.exists(project.abspath):
                self.wrn("Project {} does not exist yet, skipping...".format(project.name))
                continue
            if not path.exists(justfile_path):
                self.wrn("Skipping setup for {} (could not find {})...".format(project.name, justfile))
                continue
            self.inf("Copying {} to {}".format(justfile, path.join(project.path, "Justfile")))
            dest = path.join(project.abspath, "Justfile")
            if path.exists(dest):
                chmod(dest, S_IWUSR|S_IREAD)
            copyfile(justfile_path, dest)
            chmod(dest, S_IREAD|S_IRGRP|S_IROTH)
