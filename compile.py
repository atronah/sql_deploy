# -*- coding: utf-8 -*-
import re
import shlex
import sys
import os
import argparse
import configparser
import logging

import subprocess

import datetime

DEFAULT_ENCODING = 'utf-8'


def coroutine(func):
    def wrapper(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr

    return wrapper


@coroutine
def writer(filename, prepend=False):
    filename = os.path.abspath(filename)
    if os.path.isfile(filename):
        logging.info('remove existed file: {}'.format(filename))
        os.remove(filename)
    no_data = True
    try:
        with open(filename, 'w+' if prepend else 'w') as o:
            while True:
                data = (yield)
                if data is None:
                    break
                if data:
                    no_data = False
                data += '\n'
                if prepend:
                    o.seek(0)
                    data += o.read()
                    o.seek(0)
                o.write(data)
    except GeneratorExit:
        if no_data:
            logging.info('remove empty file: {}'.format(filename))
            os.remove(filename)
        else:
            logging.info('finished writing to the file: {}'.format(filename))


class RuleProcessor:
    def __init__(self, encoding=DEFAULT_ENCODING):
        self._settings = configparser.ConfigParser()
        self._encoding = encoding
        self._deploy_script = None
        self._drop_script = None

    @staticmethod
    def get_git_info(obj_path):
        git_info = {}

        obj_path = os.path.abspath(obj_path)
        work_dir = os.path.abspath(os.path.dirname(obj_path))
        while not os.path.ismount(work_dir):
            if os.path.isdir(os.path.join(work_dir, '.git')):
                for param, command in {'sha': 'git rev-parse HEAD',
                                       'branch': 'git rev-parse --abbrev-ref HEAD',
                                       'author': 'git log -1 --pretty="%an (%ae)" -- "{}"'.format(obj_path),
                                       'date': 'git log -1 --pretty="%ad" -- "{}"'.format(obj_path),
                                       'message': 'git log -1 --pretty=%B -- "{}"'.format(obj_path)
                                       }.items():
                    p = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, cwd=work_dir)
                    p.wait()
                    try:
                         git_info[param] = ''.join([line.decode('utf-8') for line in p.stdout.readlines()])
                    except UnicodeEncodeError:
                        git_info[param] = 'ENCODING ERROR during git info parsing'
                break
            work_dir = os.path.abspath(os.path.join(work_dir, os.pardir))
        return git_info

    @staticmethod
    def add_git_info(content, git_info):
        if not git_info:
            return content
        first_begin = re.search(r'\bbegin\b', content, re.IGNORECASE)
        if first_begin:
            return '\n'.join([content[:first_begin.end()],
                              '\n'.join(['-- generated on ' + str(datetime.datetime.now()),
                                         '-- git branch: ' + git_info['branch'],
                                         '-- git SHA-1: ' + git_info['sha'],
                                         '-- git author: ' + git_info['author'],
                                         '-- git date: ' + git_info['date'],
                                         '-- git commit message: ' + git_info['message'].replace('\n', '\n-- \t\t')
                                         ]).replace('\n\n', '\n'),
                              content[first_begin.end():]
                              ])
        return content

    @staticmethod
    def add_comments_block(content, info):
        comments = []

        name = info['name']
        object_type = info['type']
        param_type = info['param_type']

        comment = info['brief']
        if object_type and name and comment:
            comments.append('comment on {} {} is \'{}\';'.format(object_type, name, comment))

        if param_type:
            param_comment = 'comment on ' + param_type + ' {name}.{parameter} is \'{comment}\';'
            comments += [param_comment.format(name=name, **param_info)
                         for param_info in info['inputs'] + info['outputs']
                         ]

        return content if not comments \
            else content + '\n\n' + '\n'.join(comments)

    @staticmethod
    def parse_script_info(content):
        info = {'name': None,
                'type': None,
                'brief': None,
                'param_type': None,
                'inputs': [],
                'outputs': [],
                'description': None}

        # поиск блока doxygen комментариев, начинающихся с "/*!"
        match = re.search(r'/\*!(.*)\*/', content, flags=re.MULTILINE | re.DOTALL)
        if not match:
            return info
        comment_begin, comment_end = match.start(1), match.end(1)
        other_info_begin = comment_begin

        # поиск названия функции\процедуры
        type_map = {'fn': ('procedure', 'parameter'),
                    'tb': ('table', 'column'),
                    'tg': ('trigger', None),
                    'sq': ('sequence', None)
                    }

        match = re.search(r'\\(' + '|'.join(type_map.keys()) + r')\s+(\w+)', content[comment_begin:comment_end])
        if match:
            info['name'] = match.group(2)
            info['type'], info['param_type'] = type_map[match.group(1)]
            other_info_begin = max(other_info_begin, comment_begin + match.end() + 1)

        # поиск короткого описания
        info['brief'] = None
        pattern = re.compile(r'\\brief\s+(.+?)(?:\\param|(?:^\s*$))', re.S + re.M)
        match = re.search(pattern, content[comment_begin:comment_end])
        if match:
            info['brief'] = match.group(1).strip()
            other_info_begin = max(other_info_begin, comment_begin + match.end() + 1)

        info['inputs'] = []
        info['outputs'] = []
        # поиск описания параметров
        if info['param_type']:
            pattern = re.compile(r'\\param(?:\[(?P<direction>in|out)\])?\s+(?P<parameter>\w+)\s+(?P<comment>.*)')

            for match in pattern.finditer(content[comment_begin:comment_end]):
                info['outputs' if match.group('direction') == 'out' else 'inputs'].append(match.groupdict())
                other_info_begin = max(other_info_begin, comment_begin + match.end() + 1)

        info['description'] = content[other_info_begin:comment_end].strip()
        return info

    def _process_file(self, filename, params):
        logging.info('started processing file "{}"'.format(os.path.basename(filename)))

        with open(filename, 'r', encoding=self._encoding) as f:
            content = ''
            pattern = re.compile(r'create\s+(?:or alter\s+)?(procedure|trigger|table|sequence|generator)\s+(\w+)')
            for line in f:
                match = re.match(pattern, line)
                if match:
                    self._drop_script.send('drop {0} {1};'.format(*match.groups()))
                content += line
            script_info = self.parse_script_info(content)

            content = self.add_git_info(content, self.get_git_info(filename))
            content = self.add_comments_block(content, script_info)
            try:
                content = content.format(**params)
            except Exception as e:
                logging.warning('error "{0}" occured during formating content of file: "{1}"'.format(e, filename))
            self._deploy_script.send(content + '\n\n')

    def _process_rule(self, rule, params=None, parent_rules=None):
        if params is None:
            params = dict(self._settings['general']) if 'general' in self._settings else {}
        directory = params.get('directory', '.')
        if os.path.isfile(os.path.join(directory, rule)):

            self._process_file(os.path.join(directory, rule), params)
        elif rule not in self._settings.sections():
            logging.warning('rule "{}" is not defined'.format(rule))
            return False
        else:
            logging.info('started processing rule "{}"'.format(rule))
            if parent_rules is None:
                parent_rules = []
            elif rule in parent_rules:
                logging.warning('loop detected: {}'.format([rule] + parent_rules))
                return False
            if 'sources' in params:
                del params['sources']
            params.update(self._settings[rule])
            if 'sources' not in params:
                logging.warning('empty sources for rule "{}"'.format(rule))
                return False

            for sub_rule in params['sources'].split('\n'):
                self._process_rule(sub_rule,
                                   params,
                                   [rule] + parent_rules)
        return True

    def process(self, src_dir, dst_dir, rules=None, ini_filename=None):
        if not os.path.isdir(src_dir):
            logging.error('working directory "{}" not found'.format(os.path.abspath(src_dir)))
            return False
        os.chdir(src_dir)

        if not os.path.isdir(dst_dir):
            logging.info('create output directory "{}"'.format(os.path.abspath(dst_dir)))
            os.makedirs(dst_dir, exist_ok=True)

        if ini_filename is None:
            ini_filename = 'settings.ini'

        self._settings.read(ini_filename, encoding=DEFAULT_ENCODING)

        script_index = 1
        for rule in rules:
            if os.path.isfile(rule):
                script_name = rule
            elif rule in self._settings.sections():
                script_name = rule + '.sql'
            else:
                script_name = 'script_{}.sql'.format(script_index)
                script_index += 1

            self._deploy_script = writer(os.path.join(dst_dir, script_name), True)
            self._drop_script = writer(os.path.join(dst_dir, 'drop_' + script_name), True)
            self._process_rule(rule)

        self._deploy_script.close()
        self._drop_script.close()
        self._deploy_script = None
        self._drop_script = None
        return True


def main():
    parser = argparse.ArgumentParser(description='concatenates all scripts in one (script files must be utf-8 '
                                                 'and should not contains "{" and "}" except cases, when it used '
                                                 'for passing arguments from .ini')
    parser.add_argument('-d', '--dir', dest='dir', default='.'
                        , help='working directory relative to which all others paths are searched.')
    parser.add_argument('-o', '--out', dest='out', default='builds', help='output directory')
    parser.add_argument('-s', '--settings', dest='settings', default='settings.ini', help='settings file')
    parser.add_argument('rules', default=['general'], nargs='*'
                        , help='names of rules (.ini sections) to processing')
    
    options = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG)

    worker = RuleProcessor()
    worker.process(options.dir, options.out, options.rules, options.settings)

    return 0


if __name__ == '__main__':
    sys.exit(main())
