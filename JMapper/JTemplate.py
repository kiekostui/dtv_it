from abc import abstractmethod
from .utils import Logger
import json
import copy as CP
import re
from abc import ABC, abstractmethod

class JTemplateError(Exception):
    def __init__(self,msg):
        self.msg = msg
        super().__init__(self.msg)

class JTemplateBuildError(JTemplateError):
    def __init__(self, msg):
        super().__init__(msg)

class JWriteError(JTemplateError):
    def __init__(self, msg):
        super().__init__(msg)

class JTypeError(JTemplateError):
    def __init__(self, msg):
        super().__init__(msg)

class JNodePathError(JTemplateError):
    def __init__(self, msg):
        super().__init__( msg)

class JNodeTypeError(JTemplateError):
    def __init__(self, msg):
        super().__init__(msg)

class JValueError(JTemplateError):
    def __init__(self, msg):
        super().__init__(msg)


class JNodeNameError(JTemplateError):
    def __init__(self, msg):
        super().__init__(msg)


class JTemplate:
    def __init__(self, start_obj:str|dict|list, log_error= True):
        if isinstance(start_obj, str):
            try:
                obj_struct = json.loads(start_obj)
            except json.JSONDecodeError as e:
                raise JTemplateBuildError (f'\nUnable to build JTemplate object:\n- Invalid JSON syntax: {e}') from None
        elif isinstance(start_obj, dict|list):
            try:
                obj_struct = json.loads(json.dumps(start_obj))
            except TypeError as e:
                raise JTemplateBuildError(f'\nUnable to build JTemplate object:\n- Unable to serialize the object: {e}') from None
        else:
            raise JTemplateBuildError('\nUnable to build JTemplate object:\n- Invalid start object for JTemplate: must be a serializable str, a dict or a list') from None

        try:
            self.root = NodeBuilder.build(obj_struct)
        except JTemplateBuildError as e:
            raise JTemplateBuildError(f'\nUnable to build JTemplate object:\n{e}') from None

    def loads(self, path = None):
        if not path:
            path = '#'
        try:
            node = self.root.get_node(path)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None
        return node.loads()

    def dump(self, file,*,indent=0):
        if isinstance(file, str):
            try:
                with open(file, 'w') as f:
                    json.dump(self.loads(), f, indent=indent)
            except Exception as e:
                raise JWriteError(f'{e}')
        else:
            try:
                json.dump(self.loads(), file, indent=indent)
            except Exception as e:
                raise JWriteError(f'{e}')

    def add_node(self, path,*, key=None):
        try:
            return self.root.add_node(path, key=key)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def get_node(self, path):
        try:
            return self.root.get_node(path)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def get_all_nodes(self, path):
        try:
            return self.root.get_all_nodes(path)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def find(self, match, *, target='v', depth=True, isregex=False):
        try:
            return self.root.find(match, target=target, depth=depth, isregex=isregex)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def find_all(self, match, *, target='v', depth=True, isregex=False):
        try:
            return self.root.find_all(match, target=target, depth=depth, isregex=isregex)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def iter_find(self, match, *, target='v', depth=True, isregex=False):
        try:
            yield from self.root.iter_find(match,target=target, depth=depth, isregex=isregex)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def set_value(self, value,*, path=None):
        try:
            self.root.set_value(value, path=path)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def get_value(self, path):
        try:
            node = self.root.get_node(path)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None
        try:
            return node.value
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def _sub_template(self, root):
        try:
            sub = JTemplate.__new__(JTemplate)
            sub.root = root
            return sub
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None


class NodeBuilder:
    @staticmethod
    def build(data_obj, key='', parent=None):
        if isinstance(data_obj, dict):
            return DictNode(data_obj, key=key, parent=parent)
        elif isinstance(data_obj, list):
            return ListNode(data_obj, key=key, parent=parent)
        else:
            return LeafNode(data_obj, key=key, parent=parent)


class BaseNode(ABC):
    def __init__(self, start_obj, key='', parent=None):
        self._key_parent = key
        self._parent = parent
        self._raw_value = start_obj
        self._path = self._set_node_path()
        self._value = None
        self._data_nodes = {}
        self._phantom_nodes= {}
        self._private_value = None

    @abstractmethod
    def loads(self):
        pass

    @property
    @abstractmethod
    def value(self):
        pass

    @property
    @abstractmethod
    def keys(self):
        pass

    @property
    @abstractmethod
    def pkeys(self):
        pass

    @property
    @abstractmethod
    def length(self):
        pass

    @abstractmethod
    def _append_node(self, phantom_key, key=None):
        pass

    @property
    def nodetype(self):
        return self.__class__.__name__

    @property
    def raw_value(self):
        return CP.deepcopy(self._raw_value)

    @property
    def path(self):
        if self._parent is None:
            return '#'
        else:
            return '#.' + '.'.join([str(k).replace('.', r'\.') for k in self._path])

    def get_node(self, path):
        try:
            clean_path = self._clean_path(path)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None
        if not clean_path:
            return self
        if '*' in clean_path:
            raise JValueError(f'wildcard "*" not allowed in method get_node(), use get_all_nodes() to get a list of nodes')  from None
        try:
            list_node = self._find_node(clean_path)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None
        if not list_node:
            raise JNodePathError(f'Node with path "{path}" does not exists')
        else:
            return list_node[0]

    def get_all_nodes(self, path):
        try:
            clean_path = self._clean_path(path)
        except JTypeError as e:
            raise e.__class__(f' {e}') from None
        if not clean_path:
            return [self]
        return self._find_node(clean_path)

    def get_root(self):
        if self._parent is None:
            return self
        else:
            return self._parent.get_root()

    def add_node(self, path, *, key=None):
        try:
            clean_path = self._clean_path(path)
        except JTypeError as e:
            raise e.__class__(f' {e}') from None
        #path must contain at list the phantom key
        if not clean_path:
            raise JValueError(f'Error to add node to "{self.path}". Path cannot be void)') from None
        if '*' in clean_path:
            raise JValueError(f'wildcard "*" not allowed in method add_node()') from None
        if len(clean_path) == 1:
            sub_path = []
            phantom_key = clean_path[0]
        else:
            sub_path = clean_path[:-1]
            phantom_key = clean_path[-1]
        try:
            sub_node = self.get_node(sub_path)
        except JValueError as e:
            raise e.__class__(f'{e}') from None
        try:
            new_node = sub_node._append_node(phantom_key, key)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None
        return new_node

    def set_value(self, value, *, path=None):
        if not path:
            path = '#'
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise JTypeError(f'value must be a scalar data type (str, int, float, bool)')
        if path is None:
            path = ''
        try:
            node = self.get_node(path)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None
        if not isinstance(node, LeafNode):
            raise JNodeTypeError(f'Node of type "{node.__class__.__name__}" does not support set_value() method') from None
        if isinstance(value, (dict, list)):
            raise JTypeError(f'Error to set value of node {self.path}. Value must be a scalar data type')
        node._value = value

    def find(self, match, *, target='v', depth=False, isregex=False):
        try:
            return next(self.iter_find(match, target=target, depth=depth, isregex=isregex), None)
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def find_all(self, match, *, target='v', depth=False, isregex=False):
        try:
            return list(self.iter_find(match, target=target, depth=depth, isregex=isregex))
        except JTemplateError as e:
            raise e.__class__(f'{e}') from None

    def iter_find(self, match,*, target='v', depth=True, isregex=False):
        if target not in ('k', 'v'):
            raise JValueError(f'Argument Target must be one of "k" (key), "v" (value)') from None
        if match is not None and not isinstance(match, (str, int, float, bool)):
            raise JTypeError(f'match must be a scalar data type (str, int, float, bool)')
        pattern = None
        if isregex:
            if not isinstance(match, str):
                raise JTypeError(f'With argument isregex=True "match" must be a string') from None
            try:
                pattern=re.compile(match)
            except re.PatternError as e:
                raise JValueError(f'match is not a valid regular expression: {e}') from None
        yield from self._scan_tree(match, target=target, depth=depth, pattern=pattern)

    @staticmethod
    def _check_phantom_name (phantom_key):
        if not re.fullmatch(r'[a-zA-Z_]+[a-zA-Z0-9_]*', phantom_key):
            return False
        return True

    @staticmethod
    def _clean_path(path):
        if not isinstance(path, (list,str)):
            raise JTypeError('Argument path must be string or list')
        elif isinstance(path, str):
            tokenized_path = path.replace(r'\.', '__DOT__')
            cleaned_tokenized = [k.strip('# ') for k in tokenized_path.split('.') if k.strip('# ')]
        elif isinstance(path, list):
            tokenized_list = [str(k).replace(r'\.', '__DOT__') for k in path]
            cleaned_tokenized = [str(k).strip('# ') for k in tokenized_list if str(k).strip('# ')]
        clean_path = [k.replace('__DOT__', '.') for k in cleaned_tokenized]
        return clean_path

    def _set_node_path(self):
        if self._parent is None:
            return []
        else:
            return self._parent._path + [self._key_parent]

    def _find_node(self, path):
        node_list = []
        if not path:
            return [self]
        raw_key = path[0]
        sub_path = path[1:]
        if isinstance(self, LeafNode):
            return []
        if raw_key == '*':
            for k in self._data_nodes.keys():
                sub_nodes = self._data_nodes[k]._find_node(sub_path)
                node_list.extend(sub_nodes)
            return node_list
        elif raw_key == '!':
            if not isinstance(self, ListNode):
                raise JNodeTypeError(f'"{self.path}" is not a ListNode. Use of "!" for last element is allowed only for ListNode')
            if self._data_nodes:
                key = str(self.length - 1)
            else:
                return []
        else:
            key = raw_key
        if key in self._data_nodes.keys():
            node_list.extend(self._data_nodes[key]._find_node(sub_path))
        else:
            # Logger.log_message(f'key {key} not present in node {self.path}', 'ERROR')
            return []
        return node_list

    def _scan_tree(self, match,*, target='v', depth=False, pattern=None):
        for key, node in self._data_nodes.items():
            if target == 'k':
                if isinstance(self, ListNode):
                    compare_value = '__PASS__'
                else:
                    compare_value = key
            else:
                compare_value = node.loads()
            if compare_value != '__PASS__':
                if pattern:
                    if isinstance(compare_value, str) and pattern.fullmatch(compare_value):
                        yield node
                else:
                    if match == compare_value:
                        yield node
        if depth:
            for node in self._data_nodes.values():
                yield from node._scan_tree(match, target=target, depth=depth, pattern=pattern)


class LeafNode(BaseNode):
    def __init__(self, value, key='', parent=None):
        super().__init__(value, key, parent)
        self._value = self._raw_value

    def loads(self):
        return self._value

    @property
    def value(self):
        return self._value

    @property
    def keys(self):
        raise JNodeTypeError(f'LeafNode does not have keys')

    @property
    def pkeys(self):
        raise JNodeTypeError(f'LeafNode does not have phantom keys')

    @property
    def length(self):
        return 0

    def _append_node(self, phantom_key, key=None):
        raise JNodeTypeError(f'Error to add node to "{self.path}" with key "{key}". Can not add nodes to a LeafNode')



class StructureNode(BaseNode, ABC):
    def __init__(self, data_obj, key='', parent=None):
        super().__init__(data_obj, key, parent)

    @property
    @abstractmethod
    def keys(self):
        pass

    @property
    @abstractmethod
    def pkeys(self):
        pass

    @abstractmethod
    def loads(self):
        pass

    @property
    def value(self):
        raise JNodeTypeError(f'Property value not defined in {self.__class__.__name__}')

    @property
    def length(self):
        return len(self._data_nodes)

    @abstractmethod
    def _append_node(self, phantom_key, key=None):
        pass



class DictNode(StructureNode):
    def __init__(self, dict_obj, key='', parent=None):
        super().__init__(dict_obj, key, parent)
        error_list = []
        for k, v in dict_obj.items():
            ckey = k.strip('# ')
            try:
                node = NodeBuilder.build(v, ckey, self)
            except JTemplateError as e:
                error_list.append(f'{e}')
                continue
            if ckey.startswith('$'):
                if not self._check_phantom_name(ckey[1:]):
                    error_list.append(f'- Error in path "{self.path}.{k}". phantom key "{k}": name not valid.')
                    continue
                if ckey in self._phantom_nodes.keys():
                    error_list.append(f'- Error in path "{self.path}.{k}". phantom key "{k}": duplicated')
                    continue
                self._phantom_nodes[ckey] = node
            else:
                self._data_nodes[ckey] = node
        if error_list:
            raise JTemplateBuildError('\n'.join(error_list))

    def loads(self):
        return {k:v.loads() for k,v in self._data_nodes.items()}

    @property
    def keys(self):
        return list(self._data_nodes.keys())

    @property
    def pkeys(self):
        return list(self._phantom_nodes.keys())

    def _append_node(self, phantom_key, key=None):
        if not key:
            raise JNodeTypeError(f'Error to add node to "{self.path}". "key" argument is mandatory for add_node() method on a DictNode')
        if not isinstance(phantom_key, str):
            raise JTypeError(f'Error to add node to "{self.path}" with key "{key}" . Key argument must be a string')
        if key in self._data_nodes.keys():
            raise JValueError(f'Error to add node to "{self.path}" with key "{key}" . Key already exists in node')
        if phantom_key not in self._phantom_nodes.keys():
            raise JNodePathError(f'Error to add node to "{self.path}" with key "{key}". "{phantom_key}" not in node phantom keys')
        #No error possible: phantom_nodes[phantom_key] is already validated
        new_node = NodeBuilder.build(self._phantom_nodes[phantom_key].raw_value, key, self)
        self._data_nodes[key] = new_node
        return new_node


class ListNode(StructureNode):
    def __init__(self, list_obj, key='', parent=None):
        super().__init__(list_obj, key, parent)
        error_list = []
        index = 0
        or_index = 0
        for element in list_obj:
            node = None
            if isinstance(element, list):
                if element and isinstance(element[0], str):
                    if element[0].lstrip().startswith('$'):
                        if len(element) > 2 :
                            error_list.append(f'- Error in path "{self.path}.{or_index}". {str(element)}: phantom element cannot have more than two elements')
                            continue
                        pkey = element[0].strip('# ')
                        if pkey in self._phantom_nodes.keys():
                            error_list.append(f'- Error in path "{self.path}.{or_index}". phantom key "{element[0]}" duplicated in same list')
                            continue
                        if not self._check_phantom_name(pkey[1:]):
                            error_list.append(f'- Error in path "{self.path}.{or_index}". phantom key "{element[0]}" name not valid.')
                            continue
                        if len(element) == 1:
                            # None value to build a node cannot raise error
                            node = NodeBuilder.build(None, pkey, self)
                            self._phantom_nodes[pkey] = node
                        else:
                            try:
                                node = NodeBuilder.build(element[1], pkey, self)
                                self._phantom_nodes[pkey] = node
                            except JTemplateError as e:
                                error_list.append(f'{e}')
                                continue
                    else:
                        try:
                            node = NodeBuilder.build(element, str(index), self)
                            self._data_nodes[str(index)] = node
                            index += 1
                        except JTemplateError as e:
                            error_list.append(f'{e}')
                            continue
            else:
                try:
                    node = NodeBuilder.build(element, str(index), self)
                    self._data_nodes[str(index)] = node
                    index += 1
                except JTemplateError as e:
                    error_list.append(f'{e}')
            or_index += 1
        if error_list:
            raise JTemplateBuildError('\n'.join(error_list))

    def loads(self):
        return [self._data_nodes[str(i)].loads() for i in range(self.length)]

    @property
    def keys(self):
        raise JNodeTypeError(f'ListfNode does not have keys')

    @property
    def pkeys(self):
        return list(self._phantom_nodes.keys())

    def _append_node(self, phantom_key, key=None):
        if key:
            raise JNodeTypeError(f'Error to add node to "{self.path}" with key "{key}". Argument key not allowed to add node to a ListNode')
        if phantom_key not in self._phantom_nodes.keys():
            raise JValueError(f'Error to add node to "{self.path}". "{phantom_key}" not in node phantom keys')
        # No error possible: phantom_nodes[phantom_key] is already validated
        new_node = NodeBuilder.build(self._phantom_nodes[phantom_key].raw_value, str(self.length), self)
        self._data_nodes[str(self.length)] = new_node
        return new_node