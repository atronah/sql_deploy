# -*- coding: utf-8 -*-
import sys
import os
import logging
import re

logging.getLogger().setLevel(logging.INFO)

def usage():
    print('\n'.join([
            f''
            f'Usage: {os.path.split(sys.argv[0])[-1]} FILENAME',
            ]))


def write_to_file(filename, data_lines):
    # removes empty lines in the end of file
    while data_lines and not data_lines[-1].strip():
        data_lines.pop()

    if filename:
        if os.path.isfile(filename):
            logging.error(f'File {filename} already exists.. skipped')
        else:
            if len(data_lines) == 0:
                logging.warning(f'Empty script')
            with open(filename, 'w', encoding='utf-8') as result:
                result.writelines(data_lines)
                return True
    else:
        logging.warning(f'No filename for ended script')

    return False


def main():
    if len(sys.argv) != 2:
        logging.error('Incorect arguments number')
        usage()
        return 1

    source_filename = sys.argv[1]

    if not os.path.isfile(source_filename):
        logging.error(f'File "{source_filename}"" doesn''t exists')
        return 2

    create_pattern = re.compile(r'create\s+(?:or\s+alter\s+)?'
                                r'(procedure|trigger|table|sequence|generator|view|exception|index|domain)\s+'
                                r'([\w\$]+)')


    with open(source_filename, encoding='utf-8') as src:
        line_number, start_line = 0, 0
        result_lines = []
        result_filename, object_type, object_name = None, None, None

        for l in src.readlines():
            formated_line = l.lower().strip()

            create_match = create_pattern.match(formated_line)
            if create_match:
                object_type, object_name = create_match.groups()
                prefix = {'procedure': 'prc',
                          'trigger': 'trg',
                           'table': 'tbl',
                           'sequence': 'seq',
                           'generator': 'seq',
                           'view': 'vw',
                           'exception': 'exc',
                           'index': 'idx',
                           'domain': 'dmn',
                            }.get(object_type, 'ukn')
                # previous file hasn't written yet
                if result_filename:
                    if write_to_file(result_filename, result_lines):
                        logging.info(f'Script from lines {start_line}:{line_number}'
                                     f' has been written into file {result_filename}')
                    result_lines = []
                    start_line = line_number
                # get filename for current object
                result_filename = f'{prefix}_{object_name}.sql'
            elif formated_line.startswith('set term ^ ;'):
                logging.debug(f'The begining of new script has been reached in line: {line_number}')
                if result_filename:
                    if write_to_file(result_filename, result_lines):
                        logging.info(f'Script from lines {start_line}:{line_number}'
                                     f' has been written into file {result_filename}')
                    result_filename = None
                    result_lines = []
                start_line = line_number
            elif formated_line.startswith('set term ; ^'):
                logging.debug(f'The end of script has been reached in line: {line_number}')

            result_lines.append(l)

            line_number += 1

        if result_filename:
            if write_to_file(result_filename, result_lines):
                logging.info(f'Script from lines {start_line}:{line_number}'
                             f' has been written into file {result_filename}')
        logging.info(f'Finished. Processed lines: {line_number}')

    return 0


if __name__ == '__main__':
    sys.exit(main())