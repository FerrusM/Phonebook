import enum

HOST: str = ''  # Строка, представляющая либо имя хоста в нотации домена Интернета, либо IPv4-адрес.
PORT: int = 12333


class Contact:
    def __init__(self, name: str, surname: str, patronymic: str, number: str, note: str):
        self.name = name
        self.surname: str = surname
        self.patronymic: str = patronymic
        self.number: str = number
        self.note: str = note

    def __eq__(self, other) -> bool:
        if isinstance(other, Contact):
            return (self.name == other.name and self.surname == other.surname and self.patronymic == other.patronymic
                    and self.number == other.number and self.note == other.note)
        else:
            raise TypeError

    def __str__(self):
        return '{0} {1} {2} {3}{4}'.format(self.name, self.patronymic, self.surname, self.number, ' Заметка: {0}'.format(self.note))


class Filter:
    def __init__(self, field: str | None = None, text: str | None = None):
        self.field: str | None = field
        self.text: str | None = text


class Commands(enum.Enum):
    ADD = 1
    DELETE = 2
    UPDATE = 3


class ClientRequest:
    def __init__(self, command: Commands, data: Contact | Filter | None = None):
        self.command: Commands = command
        self.data: Contact | Filter | None = data


class ServerResponse:
    def __init__(self, command: Commands, flag: bool, data=None):
        self.command: Commands = command
        self.flag: bool = flag
        self.data = data
