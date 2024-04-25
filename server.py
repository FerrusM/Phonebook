import pickle
import socket
import sqlite3
import threading
from common import Contact, HOST, PORT, ClientRequest, Commands, ServerResponse, Filter


class DatabaseConnection:
    DATABASE_NAME: str = 'phonebook.db'
    TABLE: str = 'Phonebook'

    @classmethod
    def createDatabase(cls):
        """Создаёт базу данных."""
        connection = sqlite3.connect(cls.DATABASE_NAME)  # Создаем подключение к базе данных.
        cursor = connection.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS {0} (
        name TEXT NOT NULL,
        surname TEXT NOT NULL,
        patronymic TEXT NOT NULL,
        number TEXT NOT NULL,
        note TEXT,
        PRIMARY KEY (number)
        )
        '''.format(cls.TABLE))

        connection.commit()
        connection.close()

    @classmethod
    def insert(cls, pbr: Contact):
        connection = sqlite3.connect(cls.DATABASE_NAME)  # Создаем подключение к базе данных.
        cursor = connection.cursor()

        try:
            cursor.execute('INSERT INTO {0} (name, surname, patronymic, number, note) VALUES (?, ?, ?, ?, ?);'.format(cls.TABLE),
                           (pbr.name, pbr.surname, pbr.patronymic, pbr.number, pbr.note))
        except Exception as error:
            ...

        connection.commit()
        connection.close()

    @classmethod
    def delete(cls, pbr: Contact) -> bool:
        connection = sqlite3.connect(cls.DATABASE_NAME)  # Создаем подключение к базе данных.
        cursor = connection.cursor()

        cursor.execute('DELETE FROM {0} WHERE name = ? AND surname = ? AND patronymic = ? AND number = ? AND note = ?;'.format(cls.TABLE),
                       (pbr.name, pbr.surname, pbr.patronymic, pbr.number, pbr.note))

        connection.commit()
        connection.close()

        rowcount: int = cursor.rowcount
        assert rowcount == 0 or rowcount == 1
        if cursor.rowcount == 1:
            return True
        elif cursor.rowcount == 0:
            return False

    @classmethod
    def getPhones(cls) -> list[Contact]:
        phone_list: list[Contact] = []
        connection = sqlite3.connect(cls.DATABASE_NAME)  # Создаем подключение к базе данных.
        cursor = connection.cursor()

        cursor.execute('SELECT * FROM {0};'.format(cls.TABLE))
        for phone in cursor.fetchall():
            pr = Contact(name=phone[0],
                         surname=phone[1],
                         patronymic=phone[2],
                         number=phone[3],
                         note=phone[4])
            phone_list.append(pr)

        connection.close()
        return phone_list

    @classmethod
    def getFilteredPhones(cls, filter: Filter | None) -> list[Contact]:
        phone_list: list[Contact] = []
        connection = sqlite3.connect(cls.DATABASE_NAME)  # Создаем подключение к базе данных.
        cursor = connection.cursor()

        if filter is None:
            request: str = 'SELECT * FROM {0};'.format(cls.TABLE)
            cursor.execute(request)
        elif filter.field is None or filter.text is None:
            request: str = 'SELECT * FROM {0};'.format(cls.TABLE)
            cursor.execute(request)
        else:
            request: str = 'SELECT * FROM {0} WHERE {1} GLOB \'*{2}*\';'.format(cls.TABLE, filter.field, filter.text)
            cursor.execute(request)

        for phone in cursor.fetchall():
            pr = Contact(name=phone[0],
                         surname=phone[1],
                         patronymic=phone[2],
                         number=phone[3],
                         note=phone[4])
            phone_list.append(pr)

        connection.close()
        return phone_list


if __name__ == '__main__':
    stop_event = threading.Event()

    def work_with_client(client_socket: socket, client_address):
        def send(data) -> bool:
            dump = pickle.dumps(data)  # Сериализация.
            try:
                client_socket.sendall(dump)  # Отправляем данные клиенту.
            except Exception as error:
                return False
            else:  # Если исключения не было.
                return True

        with client_socket:
            while not stop_event.is_set():
                try:
                    data = client_socket.recv(1024)  # Принимаем команды от клиента.
                except Exception as error:
                    break
                else:  # Если исключения не было.
                    if data == b'':
                        break  # Клиент отключился.
                    else:
                        request: ClientRequest = pickle.loads(data)
                        if isinstance(request, ClientRequest):
                            match request.command:
                                case Commands.ADD:
                                    contact: Contact = request.data
                                    DatabaseConnection.insert(contact)
                                    response = ServerResponse(command=Commands.ADD, flag=True)
                                    send(response)
                                case Commands.DELETE:
                                    contact: Contact = request.data
                                    delete_flag: bool = DatabaseConnection.delete(contact)
                                    response = ServerResponse(command=Commands.DELETE, flag=delete_flag)
                                    send(response)
                                case Commands.UPDATE:
                                    filter: Filter | None = request.data
                                    phonebook: list[Contact] = DatabaseConnection.getFilteredPhones(filter)
                                    response = ServerResponse(command=Commands.UPDATE, flag=True, data=phonebook)
                                    send(response)

    def server_loop():
        while not stop_event.is_set():
            try:
                client_socket, client_address = listener.accept()  # Начинаем принимать соединения.
            except Exception as error:
                if not stop_event.is_set():
                    break
                else:
                    raise error
            else:
                client_thread = threading.Thread(target=work_with_client, args=(client_socket, client_address))
                client_thread.start()

    DatabaseConnection.createDatabase()  # Создаём базу данных.

    with socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM) as listener:
        host: str = ''  # Строка, представляющая либо имя хоста в нотации домена Интернета, либо IPv4-адрес.
        address: tuple[str, int] = (HOST, PORT)

        listener.bind(address)  # Связываем сокет с портом, где он будет ожидать сообщения.
        listener.listen(10)  # Указываем сколько может сокет принимать соединений.
        print('\nСервер запущен. Хост: {0}'.format(socket.gethostname()))

        threading.Thread(target=server_loop, daemon=True).start()

        while not stop_event.is_set():
            command = input('Для выхода введите "stop"\n')
            if command.lower() == 'stop':
                stop_event.set()
