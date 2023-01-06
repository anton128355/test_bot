from pickle import load, dump


class FileDescriptor:

    def __init__(self, fd_id: int, file_name: str):
        self.fd_id = fd_id
        self.file_name = file_name


class File:

    def __init__(self, name: str):
        self.name = name
        self.data = ''


class Block:

    def __init__(self, file_name: str, data: str):
        self.file_name = file_name
        self.data = data


is_mounted = False
memory = []
fd_table = [None] * 10
links = {}


def check_is_mounted(func):
    def inner_func(*args, **kwargs):
        global is_mounted
        if not is_mounted:
            return 'Not mounted'
        result = func(*args, **kwargs)
        return result

    return inner_func


def check_is_not_mounted(func):
    def inner_func(*args, **kwargs):
        global is_mounted
        if is_mounted:
            return 'Already mounted'
        result = func(*args, **kwargs)
        return result

    return inner_func


def check_is_link(func):
    def inner_func(name, *args):
        global links
        if name in links:
            name = links[name]
        result = func(name, *args)
        return result

    return inner_func


@check_is_not_mounted
def _mount():
    global is_mounted, memory
    is_mounted = True
    with open('file_system.img', 'rb') as file_system:
        files = load(file_system)
        for file_name in files:
            if files[file_name].data:
                for block_data in range(0, len(files[file_name].data), 8):
                    memory.append(Block(file_name, files[file_name].data[block_data:block_data + 8]))
            else:
                memory.append(Block(file_name, ''))
        return 'Mounted'


@check_is_mounted
def _umount():
    global is_mounted, memory, fd_table
    is_mounted = False
    for fd in range(len(fd_table)):
        fd_table[fd] = None
    with open('file_system.img', 'wb') as file_system:
        files = {}
        for block in memory:
            if block.file_name not in files:
                files[block.file_name] = File(block.file_name)
            files[block.file_name].data += block.data
        dump(files, file_system)
        memory.clear()
        return 'Unmounted'


def _filestat(fd_id=None):
    if isinstance(fd_id, str) and fd_id.isdigit():
        global fd_table
        fd_id = int(fd_id)
        for fd in fd_table:
            if fd and fd.fd_id == fd_id:
                file_size = 0
                for block in memory:
                    if block.file_name == fd.file_name:
                        file_size += len(block.data)
                return f'{fd.fd_id: >2}   {file_size}   {fd.file_name}'
    return 'Not valid descriptor'


@check_is_mounted
def _ls():
    global memory, links
    files = []
    for block in memory:
        if block.file_name not in files:
            files.append(block.file_name)
    if not files:
        return 'Empty set'
    else:
        for file_name in files:
            for fd in fd_table:
                if fd and fd.file_name == file_name:
                    print(f'{fd.fd_id: >2}', end='   ')
                    break
            else:
                print('--', end='   ')
            print(file_name)
        return 'Ok'


@check_is_mounted
def _create(name=None):
    if isinstance(name, str):
        for block in memory:
            if block.file_name == name:
                return 'Filename already in use'
        memory.append(Block(name, ''))
        return f'File {name} created'
    return 'Not valid name'


@check_is_link
def _open(name=None):
    if isinstance(name, str):
        global memory, fd_table
        for block in memory:
            if block.file_name == name:
                curr_fd_id, pos = -1, -1
                for fd in range(len(fd_table)):
                    if not fd_table[fd]:
                        pos = fd
                    elif fd_table[fd].fd_id > curr_fd_id:
                        curr_fd_id = fd_table[fd].fd_id
                if pos == -1:
                    return 'Too many files'
                new_fd = FileDescriptor(curr_fd_id + 1, name)
                fd_table[pos] = new_fd
                return f'{name} opened'
    return 'Not valid name'


def _close(fd_id=None):
    if isinstance(fd_id, str) and fd_id.isdigit():
        global fd_table
        fd_id = int(fd_id)
        for fd in range(len(fd_table)):
            if fd_table[fd] and fd_table[fd].fd_id == fd_id:
                file_name = fd_table[fd].file_name
                fd_table[fd] = None
                return f'{file_name} closed'
    return 'Not valid descriptor'


def _read(fd_id, offset, size):
    global memory, fd_table
    for fd in fd_table:
        fd_id, offset, size = int(fd_id), int(offset), int(size)
        if fd and fd.fd_id == fd_id:
            block_number, result = 0, ''
            for block in memory:
                if block.file_name == fd.file_name:
                    result += block.data
                    block_number += 1
            return result[offset:size]
    return 'Not valid descriptor'


def _write(fd_id, offset, size):
    global memory, fd_table
    for fd in fd_table:
        fd_id, offset, size = int(fd_id), int(offset), int(size)
        if fd and fd.fd_id == fd_id:
            block_number, data = 0, '0' * size
            for block in memory:
                if block.file_name == fd.file_name:
                    new_data = (block.data[:offset - block_number * 8 - 1] +
                                data[:(block_number + 1) * 8 - offset - block_number * 8])
                    block.data = new_data
                    data = data[(block_number + 1) * 8 - offset - block_number * 8:]
                    block_number += 1
            for token in range(0, len(data), 8):
                memory.append(Block(fd.file_name, data[token:token + 8]))
            return 'Overwritten with 0'
    return 'Not valid descriptor'


@check_is_link
def _link(name, lnk):
    global memory, links
    for block in memory:
        if block.file_name == name:
            for block_ in memory:
                if block_.file_name == lnk:
                    return 'Filename already in use'
            memory.append(Block(lnk, ''))
            links[lnk] = name
            return f'Link {lnk} to file {name} created'
    return 'File not found'


def _unlink(lnk):
    global memory, links
    if isinstance(lnk, str):
        for block in memory:
            if block.file_name == lnk:
                memory.remove(block)
                links.pop(lnk)
                return f'Link {lnk} removed'
    return 'Link not found'


@check_is_link
def _truncate(name, size):
    global memory
    curr_size = 0
    size = int(size)
    file_found = False
    for block in memory:
        if block.file_name == name:
            file_found = True
            curr_size += len(block.data)
            if size < curr_size:
                block.data = block.data[:curr_size - size]
    if not file_found:
        return 'File not found'
    if curr_size < size:
        memory.append(Block(name, '0' * ((size - curr_size) % 8)))
        for _ in range(0, (size - curr_size) // 8, 8):
            memory.append(Block(name, '0' * 8))
    return 'Truncate successful'


def rm(name):
    global memory
    to_delete = []
    for block in memory:
        if block.file_name == name:
            to_delete.append(block)
    for block in to_delete:
        memory.remove(block)


def main():
    while True:
        try:
            inp = input(f'/> ').split(' ')
            command, args = inp[0], inp[1:]
            if command == 'exit':
                print(_umount())
                print('Bye')
                break
            elif command == 'mount':
                print(_mount())
            elif command == 'umount':
                print(_umount())
            elif command == 'filestat':
                print(_filestat(*args))
            elif command == 'ls':
                print(_ls())
            elif command == 'create':
                print(_create(*args))
            elif command == 'open':
                print(_open(*args))
            elif command == 'close':
                print(_close(*args))
            elif command == 'read':
                print(_read(*args))
            elif command == 'write':
                print(_write(*args))
            elif command == 'link':
                print(_link(*args))
            elif command == 'unlink':
                print(_unlink(*args))
            elif command == 'truncate':
                print(_truncate(*args))
            elif command == 'rm':
                rm(*args)
            else:
                print('Unknown command')
        except TypeError:
            print('Wrong command')


if __name__ == '__main__':
    main()
