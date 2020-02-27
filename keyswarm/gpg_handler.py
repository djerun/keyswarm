"""
this module interacts with the gpg binary and provides file encryption and decryption
as well as utility function like key listing and reencryption of a file tree.
"""

from functools import lru_cache
import logging
from os import path, walk, listdir
from pathlib import Path
from re import compile as re_compile, match as re_match
from subprocess import PIPE, Popen, STDOUT
from sys import exit as sys_exit


@lru_cache(maxsize=1)
def get_binary():
    """
    check the gpg binaty for its version
    if the version is 1 try the gpg2 binary
    exits the application if neither binary is present
    or reports to be version 2

    :return: the binary which returned version 2
    """
    logger = logging.getLogger()
    regex = re_compile(r'gpg \(GnuPG\) ([1-2])\..*')

    gpg_subprocess = Popen(['gpg', '--version'], stdout=PIPE, stderr=None)
    stdout, _ = gpg_subprocess.communicate()
    version = stdout.decode('utf-8').splitlines()[0]

    match = regex.match(version)
    if match:
        group = match.groups()[0]
        logger.debug('get_binary: gpg, version: %r', group)
        if group == "2":
            return 'gpg'
        if group == "1":
            gpg2_subprocess = Popen(['gpg2', '--version'], stdout=PIPE, stderr=None)
            stdout_2, _ = gpg2_subprocess.communicate()
            version_2 = stdout_2.decode('utf-8').splitlines()[0]

            m_2 = regex.match(version_2)
            if m_2:
                g_2 = m_2.groups()[0]
                logger.debug('get_binary: gpg2, version: %r', g_2)
                if g_2 == "2":
                    return 'gpg2'
    logging.getLogger().error('get_binary: unkown gpg version')
    sys_exit(1)


# noinspection DuplicatedCode
def list_packets(path_to_file):
    """
    lists all gpg public keys a respective file is encrypted to
    :param path_to_file: string - complete path to gog encrypted file
    :return: list of stings
    """
    logger = logging.getLogger(__name__)
    logger.debug('list_packets: path_to_file: %r', path_to_file)
    gpg_subprocess = Popen([get_binary(), '--pinentry-mode', 'cancel', '--list-packets',
                            path_to_file], stdout=PIPE, stderr=PIPE)
    stdout, stderr = gpg_subprocess.communicate()
    if re_match(b".*can't open.*", stderr):
        raise FileNotFoundError('can\'t open file')
    if re_match(b".*read error: Is a directory.*", stderr):
        raise ValueError('file is a directory')
    if re_match(b".*no valid OpenPGP data found.*", stderr):
        raise ValueError('no valid openpgp data found')
    stdout = stdout.split(b'\n')
    regex = re_compile(b'.*(keyid [0-9A-Fa-f]{16}).*')
    list_of_packet_ids = []
    for line in stdout:
        logger.debug('list_packets: %r', line)
        if regex.match(line):
            list_of_packet_ids.append(list(regex.search(line).groups())[0].decode('utf-8'))
    logger.debug('list_packets: list_of_packet_ids: %r', list_of_packet_ids)
    return list_of_packet_ids


def decrypt(path_to_file, gpg_home=None, additional_parameter=None, utf8=True):
    """
    Decripts a gpg encrypted file and returns the cleartext
    :param path_to_file: complete path to gpg encrypted file
    :param gpg_home: string the gpg home directory
    :param additional_parameter: do not use this parameter; for testing only
    :return: utf-8 encoded string
    """
    logger = logging.getLogger(__name__)
    logger.debug('decrypt: path_to_file: %r', path_to_file)
    logger.debug('decrypt: gpg_home: %r', gpg_home)
    logger.debug('decrypt: additional_parameter: %r', additional_parameter)
    if additional_parameter is None:
        additional_parameter = list()
    gpg_command = [get_binary(), '--quiet', *additional_parameter, '--decrypt', path_to_file]
    if gpg_home:
        gpg_command = [get_binary(), '--quiet', '--homedir', gpg_home, *additional_parameter,
                       '--decrypt', path_to_file]
    logger.debug('decrypt: gpg_command: %r', gpg_command)
    gpg_subprocess = Popen(gpg_command, stdout=PIPE, stderr=PIPE)
    stdout, stderr = gpg_subprocess.communicate()
    logger.debug('decrypt: stdout: %r', stdout)
    logger.debug('decrypt: stderr: %r', stderr)
    if stdout:
        if utf8:
            return stdout.decode('utf-8')
        return stdout

    if re_match(b".*decryption failed: No secret key.*", stderr):
        raise ValueError('no secret key')
    if re_match(b".*can't open.*No such file or directory.*", stderr):
        raise FileNotFoundError
    if re_match(b".*read error: Is a directory.*", stderr):
        raise ValueError('file is a directory')
    if re_match(b".*no valid OpenPGP data found.*", stderr):
        raise ValueError('no valid openpgp data found')
    raise Exception('unkown gpg error: %r' % (stderr,))


def encrypt(clear_text, list_of_recipients, path_to_file=None, gpg_home=None):
    """
    Encrypts a cleartext  to one or more public keys
    :param clear_text:
    :param list_of_recipients:
    :param path_to_file: if provided cyphertext is directly written to the file provided
    :param gpg_home: string gpg home directory
    :return: bytes of cyphertext or None
    """
    logger = logging.getLogger(__name__)
    logger.debug('encrypt: len(clear_text): %r', len(clear_text))
    logger.debug('encrypt: list_of_recipients: %r', list_of_recipients)
    logger.debug('encrypt: path_to_file: %r', path_to_file)
    logger.debug('encrypt: gpg_home: %r', gpg_home)
    if not list_of_recipients:
        raise ValueError('no recipients')
    if path_to_file and not path.exists(path.dirname(path_to_file)):
        raise FileNotFoundError('specified file path does not exist')
    cli_recipients = []
    for recipient in list_of_recipients:
        cli_recipients.append('-r')
        cli_recipients.append(recipient)
    gpg_command = [get_binary(), '--encrypt', '--auto-key-locate', 'local', '--trust-model',
                   'always', *cli_recipients]
    if gpg_home:
        gpg_command = [get_binary(), '--quiet', '--homedir', gpg_home, '--encrypt',
                       '--auto-key-locate', 'local', '--trust-model', 'always', *cli_recipients]
    logger.debug('encrypt: gpg_command: %r', gpg_command)
    gpg_subprocess = Popen(gpg_command, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout, stderr = gpg_subprocess.communicate(input=clear_text)
    logger.debug('encrypt: stdout: %r', stdout)
    logger.debug('encrypt: stderr: %r', stderr)
    if re_match(b'.*No such file or directory.*', stdout):
        raise FileNotFoundError
    if re_match(b'.*No public key.*', stdout):
        raise ValueError('no public key')
    if path_to_file:
        with open(path_to_file, 'bw') as file:
            file.write(stdout)
        return None
    return stdout


def get_recipients_from_gpg_id(path_to_gpg_id_file):
    """
    lists all public keys that are specified in a respective .gpg-id file
    :param path_to_gpg_id_file: complete path to .gpg-id file
    :return: list of strings
    """
    logger = logging.getLogger(__name__)
    logger.debug('get_recipients_from_gpg_id: path_to_gpg_id_file: %r', path_to_gpg_id_file)
    list_of_recipients = []
    with open(path_to_gpg_id_file, 'r') as file:
        for line in file.readlines():
            list_of_recipients.append(line.replace('\n', ''))
    logger.debug('get_recipients_from_gpg_id: return: %r', list_of_recipients)
    return list_of_recipients


# noinspection DuplicatedCode
def list_available_keys(additional_parameter=None, get_secret_keys=False):
    """
    lists all to gpg binary available public keys
    :param additional_parameter: do not use this; for testing only
    :return: list of strings
    """
    logger = logging.getLogger(__name__)
    logger.debug('list_available_keys: additional_parameter: %r', additional_parameter)
    if additional_parameter is None:
        additional_parameter = []
    command = '--list-keys' if not get_secret_keys else '--list-secret-keys'
    gpg_subprocess = Popen([get_binary(), command, *additional_parameter],
                           stdout=PIPE,
                           stderr=PIPE)
    stdout, stderr = gpg_subprocess.communicate()
    logger.debug('list_available_keys: stdout: %r', stdout)
    logger.debug('list_available_keys: stderr: %r', stderr)
    stdout = stdout.split(b'\n')
    regex = re_compile(rb'^uid\s+\[.+\]\s(.*)$')
    list_of_packet_ids = []
    for line in stdout:
        logger.debug('list_available_keys: line: %r', line)
        if regex.match(line):
            match = list(regex.search(line).groups())[0].decode('utf-8')
            logger.debug('list_available_keys: match: %r', match)
            list_of_packet_ids.append(match)
    return list_of_packet_ids


def import_gpg_keys(root_path):
    """
    try to read all keys inside the `.available-keys` directory
    directly at the root of the password store
    :param root_path: PathLike path to the password store, usually `~/.password-store`
    """
    logger = logging.getLogger(__name__)
    logger.debug('import_gpg_keys: root_path: %r', root_path)
    key_directory = Path(root_path, '.available-keys')
    logger.debug('import_gpg_keys: key_directory: %r', key_directory)
    if path.isdir(key_directory):
        logger.debug('import_gpg_keys: key directory exists')
        key_files = list(map(str, filter(lambda a: True, map(lambda a: Path(key_directory, a),
                                                             listdir(key_directory)))))
        logger.debug('%r', key_files)
        logger.debug('%r', *key_files)
        if key_files:
            gpg_subprocess = Popen([get_binary(), '--import', *key_files], stdout=PIPE, stderr=PIPE)
            stdout, stderr = gpg_subprocess.communicate()
            logger.debug('import_gpg_keys: stdout: %r', stdout)
            logger.debug('import_gpg_keys: stderr: %r', stderr)
        else:
            logger.debug('import_gpg_keys: no files in key directory')
    else:
        logger.debug('import_gpg_keys: key directory does not exist')


def write_gpg_id_file(path_to_file, list_of_gpg_ids):
    """
    creates a .gpg-id file with respective public key ids
    :param path_to_file: complete path to file
    :param list_of_gpg_ids: a list of strings
    :return: None
    """
    logger = logging.getLogger(__name__)
    logger.debug('write_gpg_id_file: path_to_file: %r', path_to_file)
    logger.debug('write_gpg_id_file: list_of_gpg_ids: %r', list_of_gpg_ids)
    with open(path_to_file, 'w') as file:
        for key_id in list_of_gpg_ids:
            file.write('{key}\n'.format(key=key_id))


def recursive_reencrypt(path_to_folder, list_of_keys, gpg_home=None, additional_parameter=None):
    """
    recursively reencrypts all files in a given path with the respective gpg public keys
    :param additional_parameter: gpg parameter - DO NOT USE THIS Except for testing purposes
    :param gpg_home: gpg_home directory to use
    :param path_to_folder: complete path to root folder
    :param list_of_keys: list of strings
    :return: None
    """
    logger = logging.getLogger(__name__)
    logger.debug('recursive_reencrypt: path_to_folder: %r', path_to_folder)
    logger.debug('recursive_reencrypt: list_of_keys: %r', list_of_keys)
    logger.debug('recursive_reencrypt: gpg_home: %r', gpg_home)
    logger.debug('recursive_reencrypt: additional_parameter: %r', additional_parameter)
    for root, _, files in walk(path_to_folder):
        if root == path_to_folder:
            for file in files:
                if file[-4:] == '.gpg':
                    file_path = path.join(root, file)
                    cleartext = decrypt(file_path, gpg_home=gpg_home,
                                        additional_parameter=additional_parameter)
                    encrypt(clear_text=cleartext.encode(),
                            list_of_recipients=list_of_keys,
                            path_to_file=file_path,
                            gpg_home=gpg_home)
        else:
            if not path.exists(path.join(root, '.gpg-id')):
                recursive_reencrypt(root, list_of_keys)
