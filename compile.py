# -*- coding: utf-8 -*-
import sys
import os
import re
import argparse
import configparser
import datetime
import subprocess
import shlex
import glob



class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


def get_git_info(obj_path):
    git_info = {}

    obj_path = os.path.abspath(obj_path)
    workdir = os.path.abspath(os.path.dirname(obj_path))
    while not os.path.ismount(workdir):
        if os.path.isdir(os.path.join(workdir, '.git')):
            for param, command in {'sha': 'git rev-parse HEAD'
                                    , 'branch': 'git rev-parse --abbrev-ref HEAD'
                                    , 'author': 'git log -1 --pretty="%an (%ae)" -- "{}"'.format(obj_path)
                                    , 'date': 'git log -1 --pretty="%ad" -- "{}"'.format(obj_path)
                                    , 'message': 'git log -1 --pretty=%B -- "{}"'.format(obj_path)
                                    }.items():

                p = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, cwd = workdir)
                p.wait()
                git_info[param] = ''.join([line.decode('utf-8') for line in p.stdout.readlines()])
            break
        workdir = os.path.abspath(os.path.join(workdir, os.pardir))
    return git_info


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


def parse_sctipt_info(content):
    info = {'name' : None
            , 'type' : None
            , 'brief' : None
            , 'param_type' : None
            , 'inputs' : []
            , 'outputs' : []
            , 'description' : None
        }

    # поиск блока doxygen комментариев, начинающихся с "/*!"
    match = re.search(r'/\*!(.*?)\*/', content, flags = re.MULTILINE | re.DOTALL)
    if not match:
        return info, 0, 0
    start, end = match.start(1), match.end(1)
    pos = start
    other_info_begin = pos

    # поиск названия функции\процедуры
    type_map = {'fn' : ('procedure', 'parameter')
                , 'tb' : ('table', 'column')
                , 'tg' : ('trigger', None)
                , 'sq' : ('sequence', None)}

    match = re.search(r'\\(' + '|'.join(type_map.keys()) + r')\s+(\w+)', content[pos:end])
    if match:
        info['name'] = match.group(2)
        info['type'], info['param_type'] = type_map[match.group(1)]
        other_info_begin = max(other_info_begin, pos + match.end() + 1)

    # поиск короткого описания
    info['brief'] = None
    pattern = re.compile(r'\\brief\s+(.+?)(?:\\param|(?:^\s*$))', re.S + re.M)
    match = re.search(pattern, content[pos:end])
    if match:
        info['brief'] = match.group(1).strip()
        other_info_begin = max(other_info_begin, pos + match.end() + 1)

    info['inputs'] = []
    info['outputs'] = []
    # поиск описания параметров
    if info['param_type']:
        pattern = re.compile(r'\\param(?:\[(?P<direction>in|out)\])?\s+(?P<parameter>\w+)\s+(?P<comment>.*)')

        for match in pattern.finditer(content[pos:end]):
            info['outputs' if match.group('direction') == 'out' else 'inputs'].append(match.groupdict())
            other_info_begin = max(other_info_begin, pos + match.end() + 1)

    info['description'] = content[other_info_begin:end].strip()
    return info, start, end


def add_comments_block(content, info):
    comments = []

    name = info['name']
    object_type = info['type']
    param_type = info['param_type']

    comment = info['brief']
    if object_type and name and comment:
        comments.append('comment on {} {} is \'{}\';'.format(object_type, name, comment));

    if param_type:
        param_comment = 'comment on ' + param_type + ' {name}.{parameter} is \'{comment}\';'
        comments += [param_comment.format(name = name, **param_info)
                        for param_info in info['inputs'] + info['outputs']
                    ];

    return content if not comments \
                    else content + '\n\n' + '\n'.join(comments)


def prepareFileContent(fname, encoding, params):
    content = ''
    with open(fname, 'r', encoding=encoding) as f:
        print('processing file: {}'.format(fname))

        content = f.read()
        script_info, start, end = parse_sctipt_info(content)
        content = content[:start] + (script_info['brief'] or '') + content[end:]
        content = add_git_info(content, get_git_info(fname))
        content = add_comments_block(content, script_info)
        try:
            content = content.format(**params)
        except Exception as e:
            print('error "{0}" occured during formating content of file: "{1}"'.format(e, fname))
    return content, script_info




def drop_scripts(fname, encoding):
    drop_scripts = []
    pattern = re.compile(r'create\s+(?:or alter\s+)?(procedure|trigger|table|sequence|generator)\s+(\w+)')
    with open(fname, 'r', encoding=encoding) as f:
        for line in f:
            match = re.match(pattern, line)
            if match:
                drop_scripts.append('drop {0} {1};'.format(*match.groups()))
    drop_scripts.reverse()
    return drop_scripts



def parse_file_names(source, settings):
    # if source it is rule (option from [general] section) with sections list, separated by comma
    if settings.has_option('general', source):
        print('browsing rules {}'.format(source))
        # for all sections in rule
        for section in settings['general'][source].split(','):
            section = section.strip()
            #if section not containing 'scripts' option with file names (or file patterns), skip it
            print('browsing section {}'.format(section))
            if not settings.has_option(section, 'scripts'):
                continue
            for fname_pattern in settings[section]['scripts'].split('\n'):
                for fname in glob.glob(fname_pattern):
                    yield fname
    else: #suggest, that source - it is file name or file name pattern
        for fname in glob.glob(source):
            yield fname


def makeMarkdown(info, template_file = None, encoding = None):
    content = []
    if not template_file:
        template_file = 'template.md'

    pattern = re.compile(r'{(inputs|outputs)\.\w+}')
    if os.path.isfile(template_file):
        with open(template_file, 'r', encoding=encoding) as t:
            for line in t:
                match = pattern.search(line)
                if match:
                    for param_info in info[match.group(1)]:
                        content.append(line.format(inputs = AttrDict(param_info)
                                                    , outputs = AttrDict(param_info))
                                    )
                else:
                    content.append(line.format_map(info))

    return '\n'.join(content)




def main():
    encoding = 'utf-8'
    out_dir = 'builds'

    parser = argparse.ArgumentParser(description='concatenates all scripts in one (script files must be utf-8 and shouldnt contain "{" and "}" except cases, when it used for passing arguments from .ini')
    parser.add_argument('-d', '--dir', dest='dir', default=None, help='directory with scripts')
    parser.add_argument('-o', '--out', dest='out', default=None, help='result file name')
    parser.add_argument('-s', '--settings', dest='settings', default='settings.ini', help='settings file')
    parser.add_argument('-p', '--params', dest='params', default=None
                        , help='name of sections with additional parameters for update (add/rewrite) parameters from [params] section')
    parser.add_argument('sources', default='default', nargs='*'
                        , help='name of option in [general] section with list of sections with rules for making script or file names')
    options = parser.parse_args()

    template_file = os.path.abspath('template.md')

    if options.dir:
        os.chdir(options.dir)
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    docs_dir = os.path.join(out_dir, 'docs')
    if not os.path.isdir(docs_dir):
        os.mkdir(docs_dir)

    settings = configparser.ConfigParser()
    settings.read(options.settings, encoding = encoding)

    # получение параметров для подстановки в скрипты
    params = settings['params'] if settings.has_section('params') else {}
    if settings.has_section(options.params):
        params.update(settings[options.params])

    sources = options.sources if type(options.sources) is list else [options.sources]

    if options.out is None:
        options.out = (sources[0] if settings.has_option('general', sources[0])
                                            else 'scripts') \
                      + '.sql'

    out_fullname = os.path.join(out_dir, options.out)
    with open(out_fullname, 'w', encoding = encoding) as o:
        for source in sources:
            for fname in parse_file_names(source, settings):
                content, info = prepareFileContent(fname, encoding, params)
                o.write(content + '\n\n')
                if info['name']:
                    doc_content = makeMarkdown(info, template_file, encoding = encoding)
                    doc_fname = os.path.join(docs_dir, info['name'].lower() + '.md')
                    if doc_content:
                        with open(doc_fname, 'w', encoding = encoding) as doc:
                            doc.write(doc_content)
                            print('created {}'.format(os.path.abspath(doc_fname)))

    print('created {}'.format(os.path.abspath(out_fullname)))

    drop_fullname = os.path.join(out_dir, 'drop_' + options.out)
    with open(drop_fullname, 'w', encoding = encoding) as o:
        o.write('\n'.join(drop_scripts(out_fullname, encoding)))
    print('created {}'.format(os.path.abspath(drop_fullname)))

    return 0


if __name__ == '__main__':
    sys.exit(main())
