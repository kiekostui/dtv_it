from .JTemplate import JTemplate as JT, JTemplateError, JWriteError, JTypeError, JNodePathError, JNodeTypeError, JValueError, JNodeNameError
from .utils import Logger, clean_path
from abc import ABC, abstractmethod
import copy as cp
import json
import re

NOT_VALID = object()

def check_valid(func):
    def wrapper(instance, *args, **kwargs):
        if not instance.is_valid:
            return
        return func(instance, *args, **kwargs)
    return wrapper

class JMapError(Exception):
    def __init__(self, msg):
        self.msg = msg
        super().__init__(self.msg)


class JMap:
    def __init__(self, map_input, **kwargs):
        # self.is_valid = True
        self._variables = {}
        # self._init_error = []
        self._origin_map = []
        self._directives = []
        self.report = {}
        if isinstance(map_input, str):
            try:
                map_source = json.loads(map_input)
            except json.JSONDecodeError as e:
                raise JMapError(f'Input Json not valid, invalid syntax: {e}')
                # Logger.log_message(f'Input Json not valid, invalid syntax: {e}', 'ERROR')
                # self.is_valid = False
                # return
        else:
            map_source = cp.deepcopy(map_input)
        init_error = []
        if not isinstance(map_source, list):
            raise JMapError('Input to create a map object must be a string serializable like a json array or a python list of dictionaries')
            # init_error.append('Input to create a map object must be a string serializable like a json array or a python list of dictionaries')
            # self.is_valid = False
            # return
        self.origin_map = map_source
        if kwargs:
            for key, value in kwargs.items():
                if key == '__upper__':
                    pass
                elif not value is None and not isinstance(value, (str, int, float, bool)):
                    init_error.append(f'- Not valid value for argument variable {key}. Must be a scalar data type (str, int, float, bool)')
            self._variables['__upper__'] = kwargs
        init_error.extend(self._validatemap(map_source))
        if init_error:
            raise JMapError(f'\n{"\n".join(init_error)}')

    @property
    def variables(self):
        return self._variables

    def _validatemap(self,map_source):
        # error = False
        error_list=[]
        current_index = 0
        for element in map_source:
            if not isinstance(element, dict):
                error_list.append(f'- The element in map with index {current_index} is not a dictionary')
                current_index += 1
                continue
            if len(element) != 1:
                error_list.append(f'- Wrong element with index {current_index}, dictionary cannot have more than one key')
                current_index += 1
                continue
            directive_action = next(iter(element.keys()))
            directive_origin = next(iter(element.values()))
            try:
                directive = _Directive(directive_action, directive_origin, self, current_index)
                self._directives.append(directive)
            except JMapError as e:
                error_list.append(f'- Wrong element with index {current_index}: {e}')
                current_index += 1
                continue
            current_index += 1
        return error_list


    def add_var(self, var: str):
        if not isinstance(var, str):
            raise JMapError(f'NameError: variable name must be a string')
        self._variables[var] = ''

    def solve_var(self,var):
        current_dict = self._variables
        search = True
        while search:
            for k,v in current_dict.items():
                if var == k:
                    return v
            if '__upper__' in current_dict.keys():
                current_dict = current_dict['__upper__']
            else:
                search = False
        raise JMapError(f'NameError: name {var} not defined')

    def set_var(self, var:str, value):
        current_dict = self._variables
        search = True
        while search:
            for k in current_dict.keys():
                if var == k:
                    current_dict[k] = value
                    return
            if '__upper__' in current_dict.keys():
                current_dict = current_dict['__upper__']
            else:
                search = False
        raise JMapError(f'NameError: name {var} not defined')

    def map(self, source:JT, target:JT, log_report=True):
        for directive in self._directives:
            dir_report = directive.run(source, target)
            for dir, report in dir_report.items():
                self.report[dir] = report

        if log_report:
            indent = 4
            for directive, report in self.report.items():
                report_string = f'{directive}\n'
                report_string += indent*' ' + f'Run:{report['run']}\n'
                report_string += indent*' ' + f'Origin errors: {len(report.get('origin errors', {}))}\n'
                for k, v in report.get('origin errors', {}).items():
                    report_string += 2*indent*' ' +  f'{k}: {v}\n'
                if report.get('action summary', {}):
                    #report_string += f'Action count:\n'
                    for k, v in report.get('action summary', {}).items():
                        report_string += indent*' ' + f'{k}: {v}\n'
                report_string += indent*' ' + f'Action errors: {len(report.get('action errors', {}))}\n'
                for k, v in report.get('action errors', {}).items():
                    report_string += 2*indent*' ' + f'{k}: {v}\n'
                #report_string +='\n'
                print(report_string)


class _Directive:

    def __init__(self,directive_action:str, directive_origin:str|list, jmap:JMap, index:int):
        self.map = jmap
        self.action = None
        self.origin = None
        self.index = index
        error = ''
        try:
            self.set_action(directive_action)
        except JMapError as e:
            error= error + str(e)
        try:
            self.set_origin(directive_origin)
        except JMapError as e:
            error= (error + '  --  ' + str(e)).lstrip('- ')
        if error:
            raise JMapError(error)
        self.raw_directive = '"' + directive_action + '"'
        if isinstance(directive_origin, str):
            self.raw_directive += ':' + '"' + directive_origin + '"'
        self.count_report = {
            'run': 0,
            'origin errors': {},
            'action summary': {},
            'action errors': {}
        }
        self.report = {f'{self.index} - {self.raw_directive} : ': self.count_report}


    def set_action(self, directive_action:str):
        if not isinstance(directive_action, str):
            raise JMapError(f'Action name must be a string')
        if directive_action.strip().startswith('@t'):
            try:
                self.action = _JPathMap(directive_action.strip(), self.map)
            except JMapError as e:
                raise JMapError(f'{e}')
            if self.action.is_phantom:
                raise JMapError(f'Path in directive action different than "@new" cannot point to a phantom node')
        elif directive_action.strip().startswith('@var:'):
            var_name = directive_action.strip().replace('@var:','', count=1)
            try:
                self.action = _JVarMap(var_name, self.map)
            except JMapError as e:
                raise JMapError(f'{e}')
        elif directive_action.strip().startswith('@iter:'):
            path = directive_action.strip().replace('@iter:','', count=1)
            try:
                self.action = _IterMap(path, self.map)
            except JMapError as e:
                raise JMapError(f'{e}')
        elif directive_action.strip().startswith('@new:'):
            path = directive_action.strip().replace('@new:','', count=1)
            try:
                self.action = _JNewNode(path, self.map)
            except JMapError as e:
                raise JMapError(f'{e}')
        else:
            raise JMapError('Action not valid, must start with: @t, @var:, @iter:, @new:')

    def set_origin(self, directive_origin:str|list):
        if isinstance(self.action, _IterMap):
            if not isinstance(directive_origin, list):
                raise JMapError('Origin for action @iter must be a list')
            try:
                self.origin = _JSub_Map(directive_origin, self.map)
            except JMapError as e:
                sub_error = str(e).splitlines()
                list_indented = ['    ' + line for line in sub_error]
                error = '\n'.join(list_indented)
                raise JMapError(f'Sub map not valid:\n{error}')
        else:
            if not isinstance(directive_origin, str):
                raise JMapError(f'Directive origin must be a string')
            if directive_origin.strip().startswith('@s') or directive_origin.strip().startswith('@t'):
                try:
                    self.origin = _JPathMap(directive_origin.strip(), self.map)
                except JMapError as e:
                    raise JMapError(f'{e}')
                if self.origin.has_wildcard:
                    raise JMapError(f'Path in directive origin cannot have wildcard "*"')
                if self.origin.is_phantom:
                    raise JMapError(f'Path in directive origin cannot point to a phantom node')
            elif directive_origin.strip().startswith('&'):
                var_name = directive_origin.strip().replace('&', '', count=1)
                try:
                    self.origin = _JVarRef(var_name, self.map)
                except JMapError as e:
                    raise JMapError(f'{e}')
            elif directive_origin.strip().startswith('@comp'):
                # tolleranza rispetto all'assenza dei : visto che i campi saranno univocamente identificati da '(' e ')'
                fields = directive_origin.strip().replace('@comp','', count=1).lstrip(':')
                try:
                    self.origin = _JComp(fields, self.map)
                except JMapError as e:
                    raise JMapError(f'{e}')
            elif directive_origin.strip().startswith('@regex'):
                # tolleranza rispetto all'assenza dei : visto che i campi saranno univocamente identificati da '(' e ')'
                fields = directive_origin.strip().replace('@regex','', count=1).lstrip(':')
                try:
                    self.origin = _JRegex(fields, self.map)
                except JMapError as e:
                    raise JMapError(f'{e}')
            else:
                if directive_origin.strip().startswith('@'):
                    raise JMapError(f'{directive_origin.strip()} not a valid origin in directive')
                self.origin = _JString(directive_origin, self.map)

    def run(self, source:JT, target:JT):
        self.count_report['run'] += 1
        error = False
        try:
            value = self.origin.get_value(source, target)
        except JMapError as e:
            self.count_report['origin errors'][f'{e}'] = self.count_report['origin errors'].get(f'{e}',0) + 1
            error = True
            #raise JMapError(f'{e}')
        if not error:
            try:
                action_report = self.action.execute(value, source, target)
                if isinstance(self.action, _IterMap):
                    iter_report = {}
                    for dir, report in action_report.items():
                        iter_report[f'{self.index}.{dir}'] = report
                    return {**self.report, **iter_report}
                for key, value in action_report.items():
                    self.count_report['action summary'][key] = self.count_report['action summary'].get(key,0) + value
            except JMapError as e:
                self.count_report['action errors'][f'{e}'] = self.count_report['action errors'].get(f'{e}',0) + 1
        return self.report


class _DirectiveAction(ABC):
    def __init__(self,directive_input, jmap:JMap):
        return
    @abstractmethod
    def execute(self, input, source, target):
        return


class _DirectiveOrigin(ABC):
    def __init__(self,directive_input, jmap:JMap):
        return
    @abstractmethod
    def get_value(self, source, target):
        return


class _JString(_DirectiveOrigin):
    def __init__(self,string:str, jmap:JMap):
        self.map = jmap
        self._string = string

    def get_value(self, source: JT, target: JT):
        return self._string


class _JVarRef(_DirectiveOrigin):
    def __init__(self,var_name:str, jmap:JMap):
        self.name = var_name.strip()
        self.map = jmap
        try:
            test_value = jmap.solve_var(self.name)
        except JMapError as e:
            raise JMapError(f'{e}')

    def get_value(self, source: JT, target: JT):
        #name already validated in __init__, type to be validated by specific directive
        return self.map.solve_var(self.name)


class _IterMap(_DirectiveAction):
    def __init__(self, iter_path:str, jmap:JMap):
        self.map = jmap
        if iter_path.strip().startswith('@t'):
            self.iter = '@t'
        elif iter_path.strip().startswith('@s'):
            self.iter = '@s'
        else:
            raise JMapError(f'Path {iter_path} in @iter directive not valid. Must point to target (@t) or to source (@s)')
        try:
            self.iter_path = _JPathMap(iter_path, self.map)
        except JMapError as e:
            raise JMapError(f'Path {iter_path} in @iter directive not valid: {e}')
        if self.iter_path.is_phantom:
            raise JMapError('Path in directive "@iter" cannot point to a phantom node')

    def execute(self, sub_map, source, target):
        path = self.iter_path.getpath(source, target)
        if self.iter == '@t':
            node_list = target.get_all_nodes(path)
        else:
            node_list = source.get_all_nodes(path)
        if not node_list:
            raise JMapError('Path for iteration not found')
        iter_report = {}
        for node in node_list:
            if self.iter == '@t':
                sub_source = source
                sub_target = target._sub_template(node)
            else:
                sub_target = target
                sub_source = source._sub_template(node)
            key = node._path[-1] #len non puo' essere zero perchè @iter non funziona sui leafnodes
            #reset delle variabili locali ad ogni iterazione
            for var in sub_map._variables.keys():
                if var != '__upper__':
                    sub_map._variables[var]=''
            sub_map.set_var('_key', key)
            sub_map.map(sub_source, sub_target, log_report=False)

        return sub_map.report



class _JSub_Map(_DirectiveOrigin):
    def __init__(self,map_list, jmap:JMap):
        self.raw_map = map_list
        try:
            self.map = JMap(self.raw_map, _key=None, __upper__ = jmap._variables, )
        except JMapError as e:
            raise JMapError(f'{e}'.lstrip('\n'))

    def get_value(self, source, target):
        ###########source e target passati solo per omogeneità del metodo get_value############
        return self.map



class _JNewNode(_DirectiveAction):
    def __init__(self,stringpath:str, jmap):
        if not stringpath.strip().startswith('@t'):
            raise JMapError(f'Path {stringpath} in directive @new not valid: must point to target')
        try:
            self.path = _JPathMap(stringpath, jmap)
        except JMapError as e:
            raise JMapError(f'Path {stringpath} in directive @new not valid: {e}')
        if not self.path.is_phantom:
            raise JMapError(f'Path {stringpath} in directive @new not valid: not a phantom path')
        if self.path.has_wildcard:
            raise JMapError(f'Path {stringpath} in directive @new not valid: wildcard "*" not allowed')

    def execute(self, key, source, target):
        if not isinstance(key, str):
            raise JMapError(f'Key is not a string')
        try:
            self.path.new_node(key, target)
        except JValueError as e:
            raise JMapError('Duplicated key')
        except JNodePathError:
            raise JMapError('Node not found')
        except JNodeTypeError:
            if not key:
                raise JMapError('Phantom node is not a ListNode')
            else:
                raise JMapError('Phantom node is not a DictNode')
        return {'new node created': 1}


class _JPathMap(_DirectiveAction, _DirectiveOrigin):
    def __init__(self,stringpath:str, jmap:JMap):
        assert(isinstance(stringpath, str)), 'Input to _JPath is a string'
        self.is_phantom = False
        self.has_wildcard = False
        self.origin_path = stringpath
        self.is_static = True
        self.path_list = []
        self.rawpath= []
        self.jmap = jmap
        if stringpath.startswith('@t'):
            self.template_ref = '@t'
        elif stringpath.startswith('@s'):
            self.template_ref = '@s'
        else:
            raise JMapError(f'path must point to target (@t) or source (@s)')
        cleanpath = clean_path(stringpath.replace(self.template_ref, '', count=1))
        i = 0
        last = len(cleanpath) - 1
        for element in cleanpath:
            if element == '*':
                self.has_wildcard = True
            if i == last:
                if element.startswith('$'):
                    self.is_phantom = True
            if element.startswith('&'):
                try:
                    var_ref = _JVarRef(element.lstrip('&'), self.jmap)
                    self.path_list.append(var_ref)
                    self.rawpath.append(element)
                    self.is_static = False
                except JMapError as e:
                    raise JMapError(f'Not valid element {element} in path {self.origin_path}: {e}')
            else:
                string = _JString(element, self.jmap)
                self.path_list.append(string)
                self.rawpath.append(element)
            i+= 1

    def getpath(self, source:JT, target:JT):
        if self.is_static:
            return self.rawpath
        else:
            #Variable names already validated with __init__
            return [element.get_value(source, target) for element in self.path_list]

    def get_value(self, source, target):
        path = self.getpath(source, target)
        if self.template_ref == '@t':
            template = target
        else:
            template = source
        try:
            node = template.get_node(path)
        except JNodePathError:
            raise JMapError('Path not found')
        except JNodeTypeError:
            raise JMapError('Wrong node type: not a list')
        try:
            return node.value
        except JNodeTypeError:
            raise JMapError('Wrong node type. not a LeafNode')

    def execute(self, value, source, target):
        path = self.getpath(source, target)
        if self.template_ref == '@t':
            template = target
        else:
            template = source
        nodes = template.get_all_nodes(path)
        if not nodes:
            raise JMapError('Path not found')
        fault = 0
        for node in nodes:
            try:
                node.set_value(value)
            except JTemplateError as e:
                fault +=1
        return {'Nodes processed': len(nodes), 'fault': fault}

    def new_node(self, key, target):
        ####### la clase chiamante ha già verificato che è un phantom path#########
        #if self.template_ref == '@s':  #check already made by __init__ of @new
            #raise JMapError(f'path {self.origin_path} point to a source node')
        path = self.getpath(None, target)
        try:
            target.add_node(path, key=key)
        except JTemplateError as e:
            raise JMapError(f'{e}')


class _JVarMap(_DirectiveAction):
    def __init__(self, var_name:str, jmap:JMap):
        self.map = jmap
        if not re.fullmatch(r'^[A-Za-z_][A-Za-z0-9_]*', var_name):
            raise JMapError(f'Invalid variable name: {var_name}')
        self.name = var_name
        if self.name in self.map._variables:
            ################### valutare se necessario visto che potrebbe essere una semplice riassegnazione del valore########
            raise JMapError(f'Variable {self.name} already exists')
        else:
            self.map.add_var(self.name)

    def execute(self, value, source, target):
        ########surce e target passati solo per omogeneità del metodo execute##########
        try:
            self.map.set_var(self.name, value)
        except JMapError as e:
            raise JMapError(f'{e}')
        return {'assignements': 1}


class _JRegex(_DirectiveOrigin):
    def __init__(self,rx_pair:str, jmap:JMap):
        #self.path = None
        self.match = None
        self.pattern = None
        self.is_static_pattern = True
        self.map = jmap
        if not rx_pair.strip().startswith('(') or not rx_pair.strip().endswith(')'):
            raise JMapError(f'Syntax error in regex "{rx_pair}". Missing round bracket at the start or at the end')
        tokenized_rx = rx_pair.strip().replace(r'\,', '__COMMA__')[1:-1] #rimuove solo prima e ultima parentesi
        split_rx_pair = tokenized_rx.split(',')
        if len(split_rx_pair) < 2:
            raise JMapError(f'Syntax error in regex directive "{rx_pair}". Path and pattern must passed separated by comma "(path, pattern)"')
        if len(split_rx_pair) > 2:
            raise JMapError(f'Too much elements in regex directive "{rx_pair}". Comma that are not separator must be escaped')
        match_string = split_rx_pair[0].replace('__COMMA__', ',').strip()
        regex_string = split_rx_pair[1].replace(r'__COMMA__', ',').strip()
        if not match_string:
            raise JMapError(f'Missing path in regex directive "{rx_pair}"')
        if not regex_string:
            raise JMapError(f'Missing value in regex directive "{rx_pair}"')
        if match_string.startswith('@t') or match_string.startswith('@s'):
            try:
                self.match = _JPathMap(match_string, self.map)
            except JMapError as e:
                raise JMapError(f'Not valid path in regex {rx_pair}. {e}')
            if self.match.is_phantom:
                raise JMapError(f'Path in regex cannot point to a phantom node')
            if self.match.has_wildcard:
                raise JMapError(f'Path in regex cannot have wildcard "*"')
        elif match_string.startswith('&'):
            try:
                self.match = _JVarRef(match_string.lstrip('&'), self.map)
            except JMapError as e:
                raise JMapError(f'Not valid match in regex {rx_pair}. {e}')
        else:
            raise JMapError(f'Error in regex: {rx_pair}: match object must be a path to a source, a path to a target, or a reference to a variable')
        if regex_string.strip().startswith('&'):
            self.is_static_pattern = False
            try:
                self.pattern = _JVarRef(regex_string.strip().lstrip('&'), self.map)
            except JMapError as e:
                raise JMapError(f'Not valid regex in "{rx_pair}": {e}')
        else:
            try:
                self.pattern = re.compile(regex_string)
            except re.PatternError as e:
                self.is_valid = False
                raise JMapError(f'Not valid regex in "{rx_pair}": {e}')
            if self.pattern.groups != 1:
                raise JMapError(f'Not valid regex in "{rx_pair}": pattern must contains exactly one capturing group')

    def get_value(self, source: JT, target: JT):
        try:
            text = self.match.get_value(source, target)
        except JMapError as e:
            raise JMapError(f'{e}')
        if not isinstance(text, str):
            raise JMapError('Match not a string')
        pattern = ''
        if self.is_static_pattern:
            pattern = self.pattern
        else:
            #pattern is a ref variabile and cannot raise exceptions at runtime
            pattern_string = self.pattern.get_value(source, target)
            if not isinstance(pattern_string, str):
                raise JMapError('Pattern not a string')
            try:
                pattern = re.compile(pattern_string)
            except re.PatternError as e:
                raise JMapError(f'Error in compile pattern')
            if pattern.groups != 1:
                raise JMapError(f'Error in capturing group number')
        result = pattern.search(text)
        if result:
            return result.group(1)
        else:
            raise JMapError(f'No Match')


class _JComp(_DirectiveOrigin):
    def __init__(self, str_parts:str, jmap:JMap):
        self.parts = []
        if not str_parts.strip().startswith('(') or not str_parts.strip().endswith(')'):
            raise JMapError(f'Syntax error in directive "{str_parts}". Missing round bracket at the start or at the end')
        tokenized = str_parts.strip().replace(r'\,', '__COMMA__').replace(r'\ ','__SPACE__')[1:-1] #rimuove solo la prima e l'ultima parentesi
        list_parts = [s.strip() for s in tokenized.split(',')]
        for element in list_parts:
            text =  element.replace('__COMMA__', ',').replace('__SPACE__', ' ')
            if element.startswith('@s') or element.startswith('@t'):
                try:
                    path = _JPathMap(element.strip(), jmap)
                    self.parts.append(path)
                except JMapError as e:
                    self.is_valid = False
                    raise JMapError(f'path "{element}" in {str_parts} not valid: {e}')
                if path.is_phantom:
                    raise JMapError(f'Path in @comp cannot point to a phantom node')
                if path.has_wildcard:
                    raise JMapError(f'Path in @comp cannot have wildcard "*"')
            elif element.startswith('&'):
                try:
                    var = _JVarRef(element.lstrip('&'), jmap)
                    self.parts.append(var)
                except JMapError as e:
                    self.is_valid = False
                    raise JMapError(f'Variable reference "{element}" in {str_parts} not valid: {e}')
            else:
                string = _JString(text, jmap)
                self.parts.append(string)

    def get_value(self,source: JT, target: JT):
        value_list = []
        error_list = []
        i = 0
        for element in self.parts:
            try:
                value = element.get_value(source, target)
                if isinstance(value, (int, float)):
                    value = str(value)
                if not isinstance(value, str):
                    raise JMapError(f'Index {i} type not valid (valid types: str, int, float)')
                value_list.append(value)
            except JMapError as e:
                raise JMapError(f'Error in index {i}: {e}')
        return ''.join(value_list)