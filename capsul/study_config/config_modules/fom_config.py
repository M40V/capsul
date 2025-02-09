##########################################################################
# CAPSUL - Copyright (C) CEA, 2013
# Distributed under the terms of the CeCILL-B license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
# for details.
##########################################################################

'''
Config module for :mod:`File Organization models (FOMs) <capsul.attributes.fom_completion_engine>`

Classes
=======
:class:`FomConfig`
------------------
'''

import os
import six
from traits.api import Bool, Str, Undefined
from soma.fom import AttributesToPaths, PathToAttributes
from soma.application import Application
from capsul.study_config.study_config import StudyConfigModule
from soma.sorted_dictionary import SortedDictionary


class FomConfig(StudyConfigModule):
    '''FOM (File Organization Model) configuration module for StudyConfig

    Note: FomConfig needs BrainVISAConfig to be part of StudyConfig modules.
    '''

    dependencies = ['BrainVISAConfig', 'SPMConfig', 'AttributesConfig']

    def __init__(self, study_config, configuration):
        super(FomConfig, self).__init__(study_config, configuration)
        self.study_config.add_trait('input_fom', Str(Undefined, output=False,
            desc='input FOM'))
        self.study_config.add_trait('output_fom', Str(Undefined, output=False,
            desc='output FOM'))
        self.study_config.add_trait('shared_fom', Str(Undefined, output=False,
            desc='shared data FOM'))
        self.study_config.add_trait('volumes_format',
                                    Str(Undefined, output=False,
            desc='Format used for volumes'))
        self.study_config.add_trait('meshes_format',
                                    Str(Undefined, output=False,
            desc='Format used for meshes'))
        self.study_config.add_trait(
            'auto_fom',
            Bool(True, output=False,
                 desc='Look in all FOMs when a process is not found'))
        self.study_config.add_trait('use_fom', Bool(
            Undefined,
            output=False,
            desc='Use File Organization Models for file parameters '
                'completion'))

        # defaults
        self.study_config.input_fom = ""
        self.study_config.output_fom = ""
        self.study_config.shared_fom = ""


    def initialize_module(self):
        '''Load configured FOMs and create FOM completion data in
        self.study_config.modules_data
        '''
        if self.study_config.use_fom is False:
            return
        
        soma_app = Application('capsul', plugin_modules=['soma.fom'])
        if 'soma.fom' not in soma_app.loaded_plugin_modules:
            # WARNING: this is unsafe, may erase configured things, and
            # probably not thread-safe.
            soma_app.initialize()
        self.study_config.modules_data.foms = {}
        self.study_config.modules_data.all_foms = SortedDictionary()
        self.study_config.modules_data.fom_atp = {'all': {}}
        self.study_config.modules_data.fom_pta = {'all': {}}

        foms = (('input', self.study_config.input_fom),
                ('output', self.study_config.output_fom),
                ('shared', self.study_config.shared_fom))
        for fom_type, fom_filename in foms:
            if fom_filename != "":
                fom, atp, pta = self.load_fom(fom_filename)
                self.study_config.modules_data.foms[fom_type] = fom
                self.study_config.modules_data.fom_atp[fom_type] = atp
                self.study_config.modules_data.fom_pta[fom_type] = pta

        self.study_config.use_fom = True
        self.update_module()


    def update_module(self):
        if not self.study_config.use_fom:
            return

        modules_data = self.study_config.modules_data

        if self.study_config.auto_fom \
                and len(modules_data.all_foms) <= 3:
            soma_app = Application('capsul', plugin_modules=['soma.fom'])
            for schema in soma_app.fom_manager.find_foms():
                if schema not in modules_data.all_foms:
                    modules_data.all_foms[schema] = None # not loaded yet.

        foms = (('input', self.study_config.input_fom),
                ('output', self.study_config.output_fom),
                ('shared', self.study_config.shared_fom))
        for fom_type, fom_filename in foms:
            if fom_filename != "":
                fom = self.study_config.modules_data.all_foms.get(fom_filename)
                if fom is None:
                    fom, atp, pta = self.load_fom(fom_filename)
                else:
                    atp = self.study_config.modules_data.fom_atp['all'] \
                        [fom_filename]
                    pta = self.study_config.modules_data.fom_pta['all'] \
                        [fom_filename]
                self.study_config.modules_data.foms[fom_type] = fom
                self.study_config.modules_data.fom_atp[fom_type] = atp
                self.study_config.modules_data.fom_pta[fom_type] = pta

        # update directories
        directories = {}
        directories['spm'] = self.study_config.spm_directory
        directories['shared'] = self.study_config.shared_directory
        directories['input'] = self.study_config.input_directory
        directories['output'] = self.study_config.output_directory

        for atp in modules_data.fom_atp['all'].values():
            atp.directories = directories


    def update_formats(self):
        directories = {}
        directories['spm'] = self.study_config.spm_directory
        directories['shared'] = self.study_config.shared_directory
        directories['input'] = self.study_config.input_directory
        directories['output'] = self.study_config.output_directory

        for schema, fom in self.study_config.modules_data.all_foms.items():
            formats = tuple(getattr(self.study_config, key) \
                for key in self.study_config.user_traits() \
                if key.endswith('_format') \
                    and getattr(self.study_config, key) is not Undefined)

            atp = AttributesToPaths(
                fom,
                selection={},
                directories=directories,
                preferred_formats=set((formats)))
            old_atp = self.study_config.modules_data.fom_atp['all'].get(schema)
            self.study_config.modules_data.fom_atp['all'][schema] = atp
            if old_atp is not None:
                for t in ('input', 'output', 'shared'):
                    if self.study_config.modules_data.fom_atp.get(t) is old_atp:
                        self.study_config.modules_data.fom_atp[t] = atp

    def load_fom(self, schema):
        soma_app = Application('capsul', plugin_modules=['soma.fom'])
        if 'soma.fom' not in soma_app.loaded_plugin_modules:
            # WARNING: this is unsafe, may erase configured things, and
            # probably not thread-safe.
            soma_app.initialize()
        fom = soma_app.fom_manager.load_foms(schema)
        self.study_config.modules_data.all_foms[schema] = fom

        # Create FOM completion data in self.study_config.modules_data
        formats = tuple(getattr(self.study_config, key) \
            for key in self.study_config.user_traits() \
            if key.endswith('_format') \
                and getattr(self.study_config, key) is not Undefined)

        directories = {}
        directories['spm'] = self.study_config.spm_directory
        directories['shared'] = self.study_config.shared_directory
        directories['input'] = self.study_config.input_directory
        directories['output'] = self.study_config.output_directory

        atp = AttributesToPaths(
            fom,
            selection={},
            directories=directories,
            preferred_formats=set((formats)))
        self.study_config.modules_data.fom_atp['all'][schema] = atp
        pta = PathToAttributes(fom, selection={})
        self.study_config.modules_data.fom_pta['all'][schema] = pta
        return fom, atp, pta

    
    def initialize_callbacks(self):
        self.study_config.on_trait_change(
            self.update_module,
            ['use_fom', 'input_directory', 'input_fom', 'meshes_format',
             'output_directory', 'output_fom', 'shared_directory',
             'shared_fom', 'spm_directory', 'volumes_format', 'auto_fom'])
        self.study_config.on_trait_change(
            self.update_formats, ['meshes_format', 'volumes_format'])

