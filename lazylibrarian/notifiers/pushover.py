# Author: Marvin Pinto <me@marvinp.ca>
# Author: Dennis Lutter <lad1337@gmail.com>
# URL: http://code.google.com/p/lazylibrarian/
#
# This file is part of LazyLibrarian.
#
# LazyLibrarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# LazyLibrarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with LazyLibrarian.  If not, see <http://www.gnu.org/licenses/>.

import base64
from httplib import HTTPException
from httplib import HTTPSConnection
import lazylibrarian
from lazylibrarian import logger
import lazylibrarian.common as common
from lazylibrarian.common import NOTIFY_DOWNLOAD
from lazylibrarian.common import NOTIFY_SNATCH
from lazylibrarian.common import notifyStrings
import time
import urllib
from urllib import urlencode
import urllib2


class PushoverNotifier:

    def _sendPushover(self, message=None, event=None, pushover_apitoken=None, pushover_keys=None, 
                      notificationType = None, method = None, force = False):

        if not lazylibrarian.USE_PUSHOVER and not force:
            return False

        if pushover_apitoken == None:
            pushover_apitoken = lazylibrarian.PUSHOVER_APITOKEN
        if pushover_keys == None:
            pushover_keys = lazylibrarian.PUSHOVER_KEYS
        method = 'POST'
        if method == 'POST':
            uri = '/api/pushes'
        else:
            uri = '/api/keys'

        logger.debug("Pushover event: " + str(event))
        logger.debug("Pushover message: " + str(message))
        logger.debug("Pushover api: " + str(pushover_apitoken))
        logger.debug("Pushover keys: " + str(pushover_keys))
        logger.debug("Pushover notification type: " + str(notificationType))

        http_handler = HTTPSConnection('api.pushover.net')

        if notificationType == None:
            testMessage = True
            try:
                logger.debug("Testing Pushover authentication and retrieving the device list.")
                http_handler.request(method, uri, None, headers={'Authorization': 'Basic %s:' % authString})
            except (SSLError, HTTPException):
                logger.error("Pushover notification failed.")
                return False
        else:
            testMessage = False
            try:
                data = {'token': lazylibrarian.PUSHOVER_APITOKEN,
                    'user': pushover_keys,
                    'title': event.encode('utf-8'),
                    'message': message.encode("utf-8"),
                    'priority': lazylibrarian.PUSHOVER_PRIORITY}
                http_handler.request("POST",
                                     "/1/messages.json",
                                     headers = {'Content-type': "application/x-www-form-urlencoded"},
                                     body = urlencode(data))
                pass
            except Exception, e:
                logger.error(str(e))
                return False

        response = http_handler.getresponse()
        request_body = response.read()
        request_status = response.status
        logger.debug("Pushover Response: %s" % request_status)
        logger.debug("Pushover Reason: %s" % response.reason)
        if request_status == 200:
            if testMessage:
                return request_body
            else:
                logger.debug("Pushover notifications sent.")
                return True
        elif request_status  >= 400 and request_status < 500:
            logger.error("Pushover reqeust failed: %s" % response.reason)
            return False
        else:
            logger.error("Pushover notification failed.")
            return False

    def _notify(self, message=None, event=None, pushover_apitoken=None, pushover_keys=None, 
                notificationType = None, method = None, force = False):
        """
        Sends a pushover notification based on the provided info or LL config

        title: The title of the notification to send
        message: The message string to send
        username: The username to send the notification to (optional, defaults to the username in the config)
        force: If True then the notification will be sent even if pushover is disabled in the config
        """
        try:
            message = common.removeDisallowedFilenameChars(message)
        except Exception, e:
            logger.warn("Pushover: could not convert  message: %s" % e)
        # suppress notifications if the notifier is disabled but the notify options are checked
        if not lazylibrarian.USE_PUSHOVER and not force:
            return False

        logger.debug("Pushover: Sending notification for " + str(message))

        self._sendPushover(message, event, pushover_apitoken, pushover_keys, notificationType, method)
        return True

##############################################################################
# Public functions
##############################################################################

    def notify_snatch(self, title):
        if lazylibrarian.PUSHOVER_ONSNATCH:
            self._notify(message=title, event=notifyStrings[NOTIFY_SNATCH], notificationType='note', method='POST')

    def notify_download(self, title):
        if lazylibrarian.PUSHOVER_ONDOWNLOAD:
            self._notify(message=title, event=notifyStrings[NOTIFY_DOWNLOAD], notificationType='note', method='POST')

    def test_notify(self, apitoken, title="Test"):
        return self._sendPushover("This is a test notification from LazyLibrarian", title, apitoken)

    def update_library(self, showName=None):
        pass

notifier = PushoverNotifier
