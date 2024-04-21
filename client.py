import enum
import pickle
import socket
import threading
from tkinter import *
from tkinter import ttk
from common import Contact, PORT, ClientRequest, Commands, ServerResponse, Filter

host: str = 'localhost'  # Строка, представляющая либо имя хоста в нотации домена Интернета, либо IPv4-адрес.
address: tuple[str, int] = (host, PORT)


class RepeatTimer(threading.Timer):
    def __init__(self, interval: float, function):
        super().__init__(interval, function)
        self.__interrupt: bool = False

    def run(self):
        while not self.finished.wait(self.interval) and not self.__interrupt:
            self.function(*self.args, **self.kwargs)

    def stop(self):
        self.__interrupt = True
        self.join()
        self.cancel()
        pass


class ClientForm(Tk):
    def __init__(self):
        super().__init__()
        self.title('Клиент')  # Заголовок окна.
        self.geometry("1200x600")  # Устанавливаем размеры окна.

        def autoupdate():
            # if not self.updateData():  # Обновляем список контактов клиента.
            #     self.connection_flag = False

            self.updateData(self.filter)  # Обновляем список контактов клиента.

        self.__updating_timer = RepeatTimer(interval=5.0, function=autoupdate)
        self.__connection_flag: bool = False
        self.__phonebook: list[Contact] = []
        self.__selected_contact: Contact | None = None

        self.connection_bar = ConnectionBar(parent=self)  # Строка подключения.
        self.connection_bar.pack(fill=BOTH, padx=2, pady=2)

        self.table = Table(parent=self)  # Таблица.
        self.table.pack(fill=BOTH, padx=2, pady=2)

        self.add_panel = AddPanel(parent=self)  # Панель добавления новой записи.
        self.add_panel.pack(side=LEFT, fill=BOTH, padx=2)

        self.search_panel = SearchPanel(parent=self)  # Панель поиска.
        self.search_panel.pack(side=LEFT, fill=BOTH, padx=2)

        self.delete_panel = DeletePanel(parent=self)  # Панель просмотра и удаления.
        self.delete_panel.pack(side=LEFT, fill=BOTH, padx=2)

        self.__selected_bind = self.table.table.bind('<<TreeviewSelect>>', self.__onSelected)

        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print('\nКлиент запущен.')
        self.connect()

    def __onSelected(self, event):
        self.selected_contact = self.table.getSelectedContact()

    @property
    def connection_flag(self) -> bool:
        return self.__connection_flag

    @connection_flag.setter
    def connection_flag(self, flag: bool):
        if self.connection_flag != flag:
            self.__connection_flag = flag
            if self.connection_flag:
                self.connection_bar.setEnabled(False)
                self.add_panel.setEnabled(True)
                if not self.updateData(self.filter):  # Обновляем список контактов клиента.
                    self.__connection_flag = False
                    self.connection_bar.setEnabled(True)
                    self.add_panel.setEnabled(False)
                else:
                    self.__updating_timer.start()
            else:
                self.add_panel.setEnabled(False)
                self.__updating_timer.stop()
                self.__socket.close()
                self.table.clear()
                self.connection_bar.setEnabled(True)

    @property
    def selected_contact(self) -> Contact | None:
        return self.__selected_contact

    @selected_contact.setter
    def selected_contact(self, contact: Contact | None):
        self.__selected_contact = contact
        self.delete_panel.setCurrentContact(self.selected_contact)

    @property
    def filter(self) -> Filter | None:
        return self.search_panel.filter

    @property
    def phonebook(self) -> list[Contact]:
        return self.__phonebook

    @phonebook.setter
    def phonebook(self, new_phonebook: list[Contact]):
        self.__phonebook = new_phonebook

        self.table.table.unbind('<<TreeviewSelect>>', self.__selected_bind)
        self.table.setData(self.phonebook)
        '''---------Восстанавливаем выбор строки---------'''
        if self.selected_contact is not None:
            self.table.selectContact(self.selected_contact)
        else:
            self.selected_contact = None
        '''----------------------------------------------'''
        self.__selected_bind = self.table.table.bind('<<TreeviewSelect>>', self.__onSelected)

    def connect(self):
        try:
            self.__socket.connect(address)  # Подключаемся к серверному сокету.
        except Exception as error:
            self.connection_flag = False
            self.connection_bar.setText('Соединение не установлено. Ошибка: {0}.'.format(error))
            print('Функция: socket.connect. Ошибка: {0}.'.format(error))
        else:  # Если исключения не было.
            self.connection_flag = True
            self.connection_bar.setText('Соединение с сервером успешно установлено.')

    def destroy(self):
        self.connection_flag = False
        super().destroy()

    def updateData(self, filter: Filter | None) -> bool:
        """Обновляет список контактов клиента."""
        print('Запрос на обновление данных.')
        request = ClientRequest(command=Commands.UPDATE, data=filter)
        dump = pickle.dumps(request)  # Сериализация.
        try:
            self.__socket.send(dump)  # Отправляем сообщение.
        except Exception as error:
            print('Функция: socket.send. Ошибка: {0}.'.format(error))
            return False
        else:  # Если исключения не было.
            try:
                data = self.__socket.recv(1024)  # Получаем список телефонных номеров.
            except Exception as error:
                print('Функция: socket.recv. Ошибка: {0}.'.format(error))
                return False
            else:  # Если исключения не было.
                if data == b'':
                    print('Сервер вернул пустой ответ!')
                    return False
                else:
                    response = pickle.loads(data)
                    if isinstance(response, ServerResponse):
                        if response.command == Commands.UPDATE:
                            if response.flag:
                                self.phonebook = response.data
                                print('Обновление данных успешно выполнено.')
                                return True
                            else:
                                print('Ошибка выполнения запроса ({0}) на сервере!'.format(response.command))
                                return False
                        else:
                            print('Ответ сервера ({0}) не соответствует запросу ({1})!'.format(response.command, Commands.UPDATE))
                            return False
                    else:
                        print('Некорректный тип сообщения от сервера ({0})!'.format(type(response)))
                        return False

    def addContact(self, new_contact: Contact) -> bool:
        """Добавляет контакт в телефонную книгу."""
        print('Запрос на добавление {0}.'.format(str(new_contact)))
        request = ClientRequest(command=Commands.ADD, data=new_contact)
        dump = pickle.dumps(request)  # Сериализация.
        try:
            self.__socket.send(dump)  # Отправляем сообщение.
        except ConnectionResetError as cre:
            print('Функция: socket.send. Ошибка: {0}.'.format(cre))
            return False
        except Exception as error:
            print('Функция: socket.send. Ошибка: {0}.'.format(error))
            return False
        else:  # Если исключения не было.
            try:
                data = self.__socket.recv(1024)  # Получаем список телефонных номеров.
            except Exception as error:
                print('Функция: socket.recv. Ошибка: {0}.'.format(error))
                return False
            else:  # Если исключения не было.
                response = pickle.loads(data)
                if isinstance(response, ServerResponse):
                    if response.command == Commands.ADD:
                        if response.flag:
                            print('Добавление успешно выполнено.')
                            return True
                        else:
                            print('Ошибка выполнения запроса ({0}) на сервере!'.format(response.command))
                            return False
                    else:
                        print('Ответ сервера ({0}) не соответствует запросу ({1})!'.format(response.command, request.command))
                        return False
                else:
                    print('Некорректный тип сообщения от сервера ({0})!'.format(type(response)))
                    return False

    def deleteContact(self, contact: Contact) -> bool:
        """Удаляет контакт из телефонной книги."""
        print('Запрос на удаление {0}.'.format(str(contact)))
        request = ClientRequest(command=Commands.DELETE, data=contact)
        dump = pickle.dumps(request)  # Сериализация.
        try:
            self.__socket.send(dump)  # Отправляем сообщение.
        except Exception as error:
            print('Функция: socket.send. Ошибка: {0}.'.format(error))
            return False
        else:  # Если исключения не было.
            try:
                data = self.__socket.recv(1024)  # Получаем список телефонных номеров.
            except Exception as error:
                print('Функция: socket.recv. Ошибка: {0}.'.format(error))
                return False
            else:  # Если исключения не было.
                response = pickle.loads(data)
                if isinstance(response, ServerResponse):
                    if response.command == Commands.DELETE:
                        if response.flag:
                            print('Удаление успешно выполнено.')
                            return True
                        else:
                            print('Ошибка выполнения запроса ({0}) на сервере!'.format(response.command))
                            return False
                    else:
                        print('Ответ сервера ({0}) не соответствует запросу ({1})!'.format(response.command, request.command))
                        return False
                else:
                    print('Некорректный тип сообщения от сервера ({0})!'.format(type(response)))
                    return False


class Columns(enum.Enum):
    """Уровень элемента в иерархической структуре."""
    surname = 'Фамилия'
    name = 'Имя'
    patronymic = 'Отчество'
    number = 'Телефонный номер'
    note = 'Заметка'


class ConnectionBar(Frame):
    """Строка подключения."""
    def __init__(self, parent: ClientForm):
        super().__init__(master=parent, borderwidth=1, relief=SOLID)

        self.status_label = Label(master=self)
        self.status_label.pack(side=LEFT)

        def onClick():
            print('Переподключение.')
            parent.connect()

        self.button = ttk.Button(master=self, text='Попробовать переподключиться', command=onClick)
        self.button.pack(side=RIGHT)

    def setEnabled(self, flag: bool):
        self.button.config(state=NORMAL if flag else DISABLED)

    def setText(self, text: str):
        self.status_label.config(text=text)


class Table(Frame):
    """Таблица."""
    def __init__(self, phones: list[Contact] | None = None, parent=None):
        super().__init__(master=parent, borderwidth=1, relief=SOLID)

        title = Label(master=self, text='ТЕЛЕФОННАЯ КНИГА')
        title.pack()

        self.table = ttk.Treeview(master=self, columns=tuple(Columns.__members__.keys()), show='headings', selectmode='browse')
        self.table.pack(fill=BOTH)

        for column in Columns:
            self.table.heading(column=str(column.name), text=column.value)

        if phones is not None:
            self.add(phones)  # Добавляем строки в таблицу.

    def clear(self):
        """Очищает таблицу."""
        self.table.delete(*self.table.get_children())

    def add(self, phones: list[Contact]):
        """Добавляет строки в таблицу."""
        for p in phones:
            self.table.insert('', END, values=(p.surname, p.name, p.patronymic, p.number, p.note))

    def setData(self, phones: list[Contact]):
        self.clear()  # Очищаем таблицу.
        self.add(phones)  # Добавляем строки в таблицу.

    @staticmethod
    def __getContactFromItem(item) -> Contact:
        values = item['values']
        assert len(values) == 5
        return Contact(name=values[1],
                       surname=values[0],
                       patronymic=values[2],
                       number=values[3],
                       note=values[4])

    @property
    def phonebook(self) -> list[Contact]:
        phonebook: list[Contact] = []
        for i in self.table.get_children():
            item = self.table.item(i)
            contact: Contact = self.__getContactFromItem(item)
            phonebook.append(contact)
        return phonebook

    def selectContact(self, contact: Contact) -> bool:
        for i in self.table.get_children():
            item = self.table.item(i)
            current_contact: Contact = self.__getContactFromItem(item)
            if current_contact == contact:
                self.table.selection_set(i)
                return True
        return False

    def getSelectedContact(self) -> Contact | None:
        """Возвращает выбранный контакт."""
        row_id_list: tuple[str, ...] = self.table.selection()
        if row_id_list:
            row_id: str = row_id_list[0]
            item = self.table.item(row_id)
            return self.__getContactFromItem(item)
        else:
            return None


class EntryBar(Frame):
    def __init__(self, text: str, parent=None):
        super().__init__(master=parent)
        label_number = Label(master=self, text=text)
        label_number.pack(side=LEFT, fill=NONE)
        self.entry_number = Entry(master=self)
        self.entry_number.pack(side=RIGHT, fill=X)

    def get(self) -> str:
        return self.entry_number.get()

    def clear(self):
        self.entry_number.delete(0, END)


class AddPanel(Frame):
    """Панель добавления новой записи."""
    def __init__(self, parent: ClientForm):
        super().__init__(master=parent, borderwidth=1, relief=SOLID)

        title = Label(master=self, text='Добавление нового номера')
        title.pack(side=TOP)

        self.frame_number = EntryBar(text='Номер:', parent=self)
        self.frame_number.pack(anchor=W, fill=X)

        self.frame_surname = EntryBar(text='Фамилия:', parent=self)
        self.frame_surname.pack(anchor=W, fill=X)

        self.frame_name = EntryBar(text='Имя:', parent=self)
        self.frame_name.pack(anchor=W, fill=X)

        self.frame_patronymic = EntryBar(text='Отчество:', parent=self)
        self.frame_patronymic.pack(anchor=W, fill=X)

        self.frame_note = EntryBar(text='Заметка:', parent=self)
        self.frame_note.pack(anchor=W, fill=X)

        def onClick():
            note: str = self.frame_note.get()  # Заметка.
            new_contact = Contact(name=self.frame_name.get(),
                                  surname=self.frame_surname.get(),
                                  patronymic=self.frame_patronymic.get(),
                                  number=self.frame_number.get(),
                                  note=note)

            if parent.addContact(new_contact):
                self.clear()
                if not parent.updateData(parent.filter):  # Обновляем список контактов клиента.
                    parent.connection_flag = False
            else:
                parent.connection_flag = False

        self.button_add = ttk.Button(master=self, text='Добавить', state=DISABLED, command=onClick)
        self.button_add.pack(side=BOTTOM)

    def setEnabled(self, flag: bool):
        self.button_add.config(state=NORMAL if flag else DISABLED)

    def clear(self):
        self.frame_number.clear()
        self.frame_surname.clear()
        self.frame_name.clear()
        self.frame_patronymic.clear()
        self.frame_note.clear()


class FieldBar(Frame):
    def __init__(self, text: str, parent=None):
        super().__init__(master=parent)
        label_title = Label(master=self, text=text)
        label_title.pack(side=LEFT, fill=NONE)
        self.label_show = Label(master=self)
        self.label_show.pack(side=RIGHT, fill=X)

    def setText(self, text: str):
        self.label_show.config(text=text)


class DeletePanel(Frame):
    """Панель просмотра и удаления."""
    def __init__(self, parent=None):
        super().__init__(master=parent, borderwidth=1, relief=SOLID)
        self.current_contact: Contact | None = None

        title = Label(master=self, text='Выбранная запись')
        title.pack(side=TOP)

        self.number_bar = FieldBar(text='Номер:', parent=self)
        self.number_bar.pack(anchor=W)

        self.surname_bar = FieldBar(text='Фамилия:', parent=self)
        self.surname_bar.pack(anchor=W)

        self.name_bar = FieldBar(text='Имя:', parent=self)
        self.name_bar.pack(anchor=W)

        self.patronymic_bar = FieldBar(text='Отчество:', parent=self)
        self.patronymic_bar.pack(anchor=W)

        self.note_bar = FieldBar(text='Заметка:', parent=self)
        self.note_bar.pack(anchor=W)

        def onClick():
            if self.current_contact is not None:
                print('Удаление {0}.'.format(str(self.current_contact)))
                if parent.deleteContact(self.current_contact):
                    if not parent.updateData(parent.filter):  # Обновляем список контактов клиента.
                        parent.connection_flag = False
                else:
                    parent.connection_flag = False

        self.button_del = ttk.Button(master=self, text='Удалить', state='disabled', command=onClick)
        self.button_del.pack(side=BOTTOM)

    def setCurrentContact(self, contact: Contact | None):
        self.button_del.config(state='disabled')
        self.current_contact = contact
        if self.current_contact is None:
            self.number_bar.setText('')
            self.surname_bar.setText('')
            self.name_bar.setText('')
            self.patronymic_bar.setText('')
            self.note_bar.setText('')
        else:
            self.number_bar.setText(contact.number)
            self.surname_bar.setText(contact.surname)
            self.name_bar.setText(contact.name)
            self.patronymic_bar.setText(contact.patronymic)
            self.note_bar.setText('' if contact.note is None else contact.note)
            self.button_del.config(state='normal')


class SearchPanel(Frame):
    """Панель поиска."""
    EMPTY_ITEM: str = '-'

    def __init__(self, parent: ClientForm):
        super().__init__(master=parent, borderwidth=1, relief=SOLID)
        self.var = StringVar()

        def __onEntryChanged(*args):
            if self.filter is not None:
                print('*Поиск \"{0}\" в столбце {1}*'.format(self.filter.text, self.filter.field))
            parent.updateData(filter=self.filter)  # Обновляем список контактов клиента.

        self.var.trace("w", __onEntryChanged)

        title = Label(master=self, text='Поиск')
        title.pack(side=TOP)

        def onSelected(event):
            if self.filter is not None:
                print('*Поиск \"{0}\" в столбце {1}*'.format(self.filter.text, self.filter.field))
            parent.updateData(filter=self.filter)  # Обновляем список контактов клиента.

        field_frame = Frame(master=self)
        field_label = Label(master=field_frame, text='Поле:')
        field_label.pack(side=LEFT, fill=NONE)
        items: list[str] = [self.EMPTY_ITEM]
        items.extend(tuple(column.value for column in Columns))
        self.combobox = ttk.Combobox(master=field_frame, values=items, state='readonly')
        self.combobox.current(0)
        self.combobox.pack(side=LEFT)
        field_frame.pack(side=TOP)

        search_frame = Frame(master=self)
        search_label = Label(master=search_frame, text='Поиск:')
        search_label.pack(side=LEFT, fill=NONE)
        self.entry = Entry(master=search_frame, textvariable=self.var)
        self.entry.pack(side=RIGHT, fill=X)
        search_frame.pack(side=TOP, fill=X)

        self.combobox.bind('<<ComboboxSelected>>', onSelected)

    @property
    def field(self) -> str | None:
        value: str = self.combobox.get()
        return None if value == self.EMPTY_ITEM else Columns(value).name

    @property
    def text(self) -> str | None:
        # text: str = self.entry.get()
        text: str = self.var.get()
        return text if text else None

    @property
    def filter(self) -> Filter | None:
        field: str | None = self.field
        text: str | None = self.text
        return None if field is None or text is None else Filter(field=self.field, text=self.text)


if __name__ == '__main__':
    form = ClientForm()
    form.mainloop()
