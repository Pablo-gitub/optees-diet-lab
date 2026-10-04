import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from optees_command import optees_command


class OpteesCommandTests(unittest.TestCase):
    def test_environment_overrides_config(self):
        with mock.patch.dict(os.environ,{'OPTEES_COMMAND':'/env/optees-mcp'}):
            self.assertEqual(optees_command({'optees_command':'/config/optees-mcp'}),'/env/optees-mcp')
    def test_config_used_without_environment(self):
        with mock.patch.dict(os.environ,{},clear=True):
            self.assertEqual(optees_command({'optees_command':'/config/optees-mcp'}),'/config/optees-mcp')
    def test_missing_command_is_reported(self):
        with mock.patch.dict(os.environ,{},clear=True),mock.patch('optees_command.sys.executable','/nowhere/python'),mock.patch('optees_command.shutil.which',return_value=None):
            with self.assertRaises(RuntimeError):optees_command()


if __name__=='__main__':unittest.main()
