"""
this module provides a recipient list widget based on QLitsWidget
"""

# pylint: disable=no-name-in-module
from PySide2.QtWidgets import QListWidget, QListWidgetItem
from PySide2.QtCore import Qt
from .gpg_handler import list_available_keys


# pylint: disable=too-few-public-methods
class Recipient(QListWidgetItem):
    """
    extends QListWidgetItem with a constructor providing
    flags for checked and enabled states
    """
    def __init__(self, name, ischecked=False, enabled=True):
        QListWidgetItem.__init__(self)
        self.setText(name)
        self.setFlags(self.flags() | Qt.ItemIsUserCheckable)
        if ischecked:
            self.setCheckState(Qt.Checked)
        else:
            self.setCheckState(Qt.Unchecked)
        if not enabled:
            self.setFlags(Qt.ItemIsUserCheckable)

    def __repr__(self):
        return (f'Recipient(name={repr(self.text())}, ischecked={repr(self.checkState())}, '
                f'enabled={repr(self.flags(Qt.ItemIsUserCheckable))}')


class RecipientList(QListWidget):
    """
    provides a list widget containing identifiers of gpg keys
    """
    def __init__(self, no_git_override=False):
        QListWidget.__init__(self)
        self.no_git_override = no_git_override
        self.setDisabled(self.no_git_override)

    def _add_recipients(self, list_of_recipient_data):
        for name, checked, enabled in list_of_recipient_data:
            self.addItem(Recipient(name, checked, enabled))

    def refresh_recipients(self, list_of_recipients):
        """
        replace all current items with all currently available keys and check the given list
        :param list_of_recipients: [str] items to check
        """
        self.clear()
        keys_available = list_available_keys()
        for key in keys_available:
            if key in list_of_recipients:
                self._add_recipients([(key, True, True)])
            else:
                self._add_recipients([(key, False, True)])
        for key in list_of_recipients:
            if key not in keys_available:
                self._add_recipients([(key, True, False)])

    def get_checked_item_names(self):
        """
        return the text of all checked items
        """
        list_of_key_ids_to_return = []
        for i in range(0, self.count()):
            item = self.item(i)
            if item.checkState():
                list_of_key_ids_to_return.append(item.text())
        return list_of_key_ids_to_return
