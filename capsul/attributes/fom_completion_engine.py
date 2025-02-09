# -*- coding: utf-8 -*-

'''
Completion engine for File Organization Models (FOM).

Classes
=======
:class:`FomProcessCompletionEngine`
-----------------------------------
:class:`FomPathCompletionEngine`
--------------------------------
:class:`FomProcessCompletionEngineIteration`
--------------------------------------------
'''

from __future__ import print_function

import os
import six
try:
    from traits.api import Str, HasTraits
except ImportError:
    from enthought.traits.api import Str, HasTraits

from soma.controller import Controller, ControllerTrait
from capsul.pipeline.pipeline import Pipeline
from capsul.pipeline.pipeline_nodes import Switch
from capsul.attributes.completion_engine import ProcessCompletionEngine, \
    ProcessCompletionEngineFactory, PathCompletionEngine, \
    PathCompletionEngineFactory
from capsul.attributes.completion_engine_iteration \
    import ProcessCompletionEngineIteration
from capsul.pipeline.process_iteration import ProcessIteration
from capsul.attributes.attributes_schema import ProcessAttributes, \
    EditableAttributes
from soma.fom import DirectoryAsDict
from soma.path import split_path
from soma.sorted_dictionary import SortedDictionary


class FomProcessCompletionEngine(ProcessCompletionEngine):
    """
    FOM (File Organization Model) implementation of completion engine.

    * A capsul.study_config.StudyConfig also needs to be configured with FOM
      module, and selected FOMS and directories:

    ::

        from capsul.api import StudyConfig
        from capsul.study_config.config_modules.fom_config import FomConfig
        study_config = StudyConfig(modules=StudyConfig.default_modules
                                   + ['FomConfig', 'BrainVISAConfig'])
        study_config.update_study_configuration('study_config.json')

    * Only then a FomProcessCompletionEngine can be created:

    ::

        process = get_process_instance('morphologist')
        fom_completion_engine = FomProcessCompletionEngine(
            process, study_config)

    But generally this creation is handled via the
    ProcessCompletionEngine.get_completion_engine() function:

    ::

        fom_completion_engine = ProcessCompletionEngine.get_completion_engine(
            process)

    Parameters
    ----------
    name: string (optional)
        name of the process in the FOM dictionary. By default the
        process.name variable will be used.

    Methods
    -------
    create_attributes_with_fom
    """
    def __init__(self, process, name=None):
        super(FomProcessCompletionEngine, self).__init__(
            process=process, name=name)


    def get_attribute_values(self):
        ''' Get attributes Controller associated to a process

        Returns
        -------
        attributes: Controller
        '''
        if not self._rebuild_attributes \
                and self.trait('capsul_attributes') is not None \
                and hasattr(self, 'capsul_attributes'):
            return self.capsul_attributes

        schemas = self._get_schemas()
        #schemas = self.process.get_study_config().modules_data.foms.keys()
        if not hasattr(self, 'capsul_attributes'):
            self.add_trait('capsul_attributes', ControllerTrait(Controller()))
            self.capsul_attributes = ProcessAttributes(self.process, schemas)
        self._rebuild_attributes = False

        self.create_attributes_with_fom()

        return self.capsul_attributes


    def create_attributes_with_fom(self):
        """To get useful attributes by the fom"""

        process = self.process
        study_config = process.study_config
        modules_data = study_config.modules_data

        #Get attributes in input fom
        names_search_list = (self.name, process.id, process.name,
                             getattr(process, 'context_name', ''))
        capsul_attributes = self.get_attribute_values()
        matching_fom = False
        input_found = False
        output_found = False

        foms = SortedDictionary()
        foms.update(modules_data.foms)
        if study_config.auto_fom:
            # in auto-fom mode, also search in additional and non-loaded FOMs
            for schema, fom in six.iteritems(modules_data.all_foms):
                if schema not in (study_config.input_fom,
                                  study_config.output_fom,
                                  study_config.shared_fom):
                    foms[schema] = fom

        def editable_attributes(attributes, fom):
            ea = EditableAttributes()
            for attribute in attributes:
                if attribute.startswith('fom_'):
                    continue # skip FOM internals
                default_value = fom.attribute_definitions[attribute].get(
                    'default_value', '')
                ea.add_trait(attribute, Str(default_value))
            return ea

        for schema, fom in six.iteritems(foms):
            if fom is None:
                fom, atp, pta \
                    = study_config.modules['FomConfig'].load_fom(schema)
            else:
                atp = modules_data.fom_atp.get(schema) \
                    or modules_data.fom_atp['all'].get(schema)

            if atp is None:
                continue
            for name in names_search_list:
                fom_patterns = fom.patterns.get(name)
                if fom_patterns is not None:
                    break
            else:
                continue

            if not matching_fom:
                matching_fom = True
            if schema == 'input':
                input_found = True
            elif schema == 'output':
                output_found = True
            elif matching_fom in (False, True, None):
                matching_fom = schema, fom, atp, fom_patterns
            #print('completion using FOM:', schema, 'for', process)
            #break

            for parameter in fom_patterns:
                param_attributes = atp.find_discriminant_attributes(
                        fom_parameter=parameter, fom_process=name)
                if param_attributes:
                    #process_attributes[parameter] = param_attributes
                    ea = editable_attributes(param_attributes, fom)
                    try:
                        capsul_attributes.set_parameter_attributes(
                            parameter, schema, ea, {})
                    except KeyError:
                        # param already registered
                        pass

        if not matching_fom:
            raise KeyError('Process not found in FOMs')
        #print('matching_fom:', matching_fom)

        if not input_found and matching_fom is not True:
            fom_type, fom, atp, fom_patterns = matching_fom
            schema = 'input'
            for parameter in fom_patterns:
                param_attributes = atp.find_discriminant_attributes(
                        fom_parameter=parameter, fom_process=name)
                if param_attributes:
                    #process_attributes[parameter] = param_attributes
                    ea = editable_attributes(param_attributes, fom)
                    try:
                        capsul_attributes.set_parameter_attributes(
                            parameter, schema, ea, {})
                    except KeyError:
                        # param already registered
                        pass
            modules_data.foms[schema] = fom
            modules_data.fom_atp[schema] = atp
            study_config.input_fom = fom_type

        if not output_found and matching_fom is not True:
            fom_type, fom, atp, fom_patterns = matching_fom
            schema = 'output'
            for parameter in fom_patterns:
                param_attributes = atp.find_discriminant_attributes(
                        fom_parameter=parameter, fom_process=name)
                if param_attributes:
                    #process_attributes[parameter] = param_attributes
                    ea = editable_attributes(param_attributes, fom)
                    try:
                        capsul_attributes.set_parameter_attributes(
                            parameter, schema, ea, {})
                    except KeyError:
                        # param already registered
                        pass
            modules_data.foms[schema] = fom
            modules_data.fom_atp[schema] = atp
            study_config.output_fom = fom_type


        # in a pipeline, we still must iterate over nodes to find switches,
        # which have their own behaviour.
        if isinstance(self.process, Pipeline):
            attributes = self.capsul_attributes
            name = self.process.name

            for node_name, node in six.iteritems(self.process.nodes):
                if isinstance(node, Switch):
                    subprocess = node
                    if subprocess is None:
                        continue
                    pname = '.'.join([name, node_name])
                    subprocess_compl = \
                        ProcessCompletionEngine.get_completion_engine(
                            subprocess, pname)
                    try:
                        sub_attributes \
                            = subprocess_compl.get_attribute_values()
                    except:
                        try:
                            subprocess_compl = self.__class__(subprocess)
                            sub_attributes \
                                = subprocess_compl.get_attribute_values()
                        except:
                            continue
                    for attribute, trait \
                            in six.iteritems(sub_attributes.user_traits()):
                        if attributes.trait(attribute) is None:
                            attributes.add_trait(attribute, trait)
                            setattr(attributes, attribute,
                                    getattr(sub_attributes, attribute))

            self._get_linked_attributes()


    def path_attributes(self, filename, parameter=None):
        """By the path, find value of attributes"""

        pta = self.process.study_config.modules_data.fom_pta['input']

        # Extract the attributes from the first result returned by
        # parse_directory
        liste = split_path(filename)
        len_element_to_delete = 1
        for element in liste:
            if element != os.sep:
                len_element_to_delete \
                    = len_element_to_delete + len(element) + 1
                new_value = filename[len_element_to_delete:len(filename)]
                try:
                    #import logging
                    #logging.root.setLevel( logging.DEBUG )
                    #path, st, self.attributes = pta.parse_directory(
                    #    DirectoryAsDict.paths_to_dict( new_value),
                    #        log=logging ).next()
                    path, st, attributes = pta.parse_directory(
                        DirectoryAsDict.paths_to_dict( new_value) ).next()
                    break
                except StopIteration:
                    if element == liste[-1]:
                        raise ValueError(
                            '%s is not recognized for parameter "%s" of "%s"'
                            % (new_value, parameter, self.process.name))

        attrib_values = self.get_attribute_values().export_to_dict()
        for att in attributes:
            if att in attrib_values.keys():
                setattr(attrib_values, att, attributes[att])
        return attributes


    def get_path_completion_engine(self):
        '''
        '''
        return FomPathCompletionEngine()


    @staticmethod
    def _fom_completion_factory(process, name):
        ''' Factoty inserted in attributed_processFactory
        '''
        study_config = process.get_study_config()
        if study_config is None \
                or 'FomConfig' not in study_config.modules \
                or study_config.use_fom == False:
            #print("no FOM:", study_config, study_config.modules.keys())
            return None  # Non Fom config, no way it could work
        try:
            pfom = FomProcessCompletionEngine(process, name)
            return pfom
        except KeyError:
            # process not in FOM
            pass
        return None


class FomPathCompletionEngine(PathCompletionEngine):

    def attributes_to_path(self, process, parameter, attributes):
        ''' Build a path from attributes

        Parameters
        ----------
        process: Process instance
        parameter: str
        attributes: ProcessAttributes instance (Controller)
        '''
        input_fom = process.study_config.modules_data.foms['input']
        output_fom = process.study_config.modules_data.foms['output']
        input_atp = process.study_config.modules_data.fom_atp['input']
        output_atp = process.study_config.modules_data.fom_atp['output']

        #Create completion
        if process.trait(parameter).output:
            atp = output_atp
            fom = output_fom
        else:
            atp = input_atp
            fom = input_fom
        name = process.id
        names_search_list = (process.id, process.name,
                             getattr(process, 'context_name', ''))
        for fname in names_search_list:
            fom_patterns = fom.patterns.get(fname)
            if fom_patterns is not None:
                name = fname
                break
        else:
            raise KeyError('Process not found in FOMs amongst %s' \
                % repr(names_search_list))

        allowed_attributes = set(attributes.user_traits().keys())
        allowed_attributes.discard('parameter')
        allowed_attributes.discard('process_name')
        #allowed_attributes = set(attributes.get_parameters_attributes()[
            #parameter].keys())
        #allowed_attributes.discard('type')
        #allowed_attributes.discard('generated_by_parameter')
        #allowed_attributes.discard('generated_by_process')

        # Select only the attributes that are discriminant for this
        # parameter otherwise other attibutes can prevent the appropriate
        # rule to match
        parameter_attributes = atp.find_discriminant_attributes(
            fom_parameter=parameter, fom_process=name)
        d = dict((i, getattr(attributes, i)) \
            for i in parameter_attributes if i in allowed_attributes)
        d['fom_process'] = name
        d['fom_parameter'] = parameter
        d['fom_format'] = 'fom_preferred'
        path_value = None
        #path_values = []
        #debug = getattr(self, 'debug', None)
        for h in atp.find_paths(d):  # , debug=debug):
            path_value = h[0]
            # find_paths() is a generator which can sometimes generate
            # several values (formats). We are only interested in the
            # first one.
            #path_values.append(h[0])
            break

        #if len(path_values) > 0:
            #path_value = path_values[0]
        return path_value


    def open_values_attributes(self, process, parameter):
        for schema in ('input', 'output', 'shared'):
            fom = process.study_config.modules_data.foms[schema]
            atp = process.study_config.modules_data.fom_atp[schema]

            name = process.id
            names_search_list = (process.id, process.name,
                                getattr(process, 'context_name', ''))
            for fname in names_search_list:
                fom_patterns = fom.patterns.get(fname)
                if fom_patterns is not None:
                    name = fname
                    break
            else:
                continue

            values = atp.find_attributes_values()
            attributes = [k for k, v in six.iteritems(values)
                          if k not in ('fom_name', 'fom_process',
                                       'fom_parameter', 'fom_format')
                            and len(v) == 2 and v[1] == (u'', )]
            return attributes

        return None


class FomProcessCompletionEngineIteration(ProcessCompletionEngineIteration):

    def get_iterated_attributes(self):
        subprocess = self.process.process
        input_fom = subprocess.study_config.modules_data.foms['input']
        output_fom = subprocess.study_config.modules_data.foms['output']
        input_atp = subprocess.study_config.modules_data.fom_atp['input']
        output_atp = subprocess.study_config.modules_data.fom_atp['output']

        name = subprocess.id
        names_search_list = (subprocess.id, subprocess.name,
                             getattr(subprocess, 'context_name', ''))
        for fom in (input_fom, output_fom):
            for fname in names_search_list:
                fom_patterns = fom.patterns.get(fname)
                if fom_patterns is not None:
                    name = fname
                    break
            else:
                continue
            break
        else:
            raise KeyError('Process not found in FOMs amongst %s' \
                % repr(names_search_list))

        iter_attrib = set()
        if not self.process.iterative_parameters:
            params = subprocess.user_traits().keys()
        else:
            params = self.process.iterative_parameters
        for parameter in params:
            if subprocess.trait(parameter).output:
                atp = output_atp
            else:
                atp = input_atp
            parameter_attributes = set([
                x for x in atp.find_discriminant_attributes(
                    fom_parameter=parameter, fom_process=name)
                if not x.startswith('fom_')])
            iter_attrib.update(parameter_attributes)
        return iter_attrib


#class FomPathCompletionEngineFactory(PathCompletionEngineFactory):

    #factory_id = 'fom'

    #def get_path_completion_engine(self, process):
        #return FomPathCompletionEngine(process)

