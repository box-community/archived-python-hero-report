# coding: utf-8

from __future__ import unicode_literals

from .base_object import BaseObject


class User(BaseObject):
    """Represents a Box user."""

    _item_type = 'user'

    def get_enterprise_users(self, limit=100, offset=0, filter_term=None):
        """
        Get enterprise users. Requires an auth token from an enterprise admin account.

        :param limit:
            The number of records to return. (default=100, max=1000)
        :type limit:
            `int`
        :param offset:
            The record at which to start.
        :type offset:
            `int`
        :param filter_term:
            A string used to filter the results to only users starting with the filter_term in either the name or the login.
        :type event_type:
            'unicode'        
        :returns:
            JSON response from the Box /users endpoint. Returns the list of all users for the Enterprise with their
            user_id, public_name, and login if the user is an enterprise admin.
        :rtype:
            `dict`
        """
        url = 'https://api.box.com/2.0/users' #self.get_url()
        params = {
            'limit': limit,
            'offset': offset
        }
        
        if filter_term is not None:
            params['filter_term'] = filter_term
        
        box_response = self._session.get(url, params=params)
        return box_response.json()