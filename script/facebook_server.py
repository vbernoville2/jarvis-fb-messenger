#!/usr/bin/env python

import argparse # Manage program arguments
import json # Read json input
import os # Build path
import sys # Use exit calls
import signal # Catch kill
from subprocess import check_output,CalledProcessError # Run shell commands
import logging # Add logging
import fbchat # Use facebook messenger library
import unicodedata # Normalized string
import ast

class JarvisFacebookMessengerServer(fbchat.Client):
  def __init__(self, email, password, verbose=True, mute=True, getId=False, allowAll=True, allowedIdList = []):
    logging.debug("Initializing Facebook messenger server with email '{}', getId='{}', verbose='{}',  mute='{}', allowAll='{}' and allowedList='{}'.".format(str(email), str(getId), str(verbose), str(mute), str(allowAll), str(allowedIdList)))

    # Launch the Facebook messenger server
    try:
      fbchat.Client.__init__(self, email, password)
    except Exception:
      logging.error("Login failed, check email/password.")
      sys.exit(2)

    # Define the command line base to communicate with Jarvis with JSON
    self.program = ["jarvis", "-j"]

    # Initialize verbose and muted options
    self.mute_mode = mute
    self.verbose_mode = verbose
    self.getId = getId
    self.allowAll = allowAll
    self.allowedIdList = allowedIdList

  def _exec(self, args):
    # Send command to Jarvis
    flags = []
    if self.mute_mode:
      flags.append(str("-m"))
    if self.verbose_mode:
      flags.append(str("-v"))

    command = self.program + flags + args

    logging.debug("Sending command '{}' to Jarvis.".format(str(command)))

    # Get response from Jarvis
    output = ""
    try:
      output = check_output(command)
    except CalledProcessError:
      pass

    return output

  def executeOrder(self, phrase):
    # Say something to Jarvis

    # Don't send empty order to Jarvis (useless and risky)
    if phrase == "":
      return list()

    # Send order to Jarvis
    result_from_request = self._exec([str("-x"), str(phrase)]).decode('utf-8')
    try:
      return list(json.loads(result_from_request, strict=False))
    except ValueError:
      logging.warning("Can't parse '{}'".format(str(result_from_request)))
      return list()

  def properExit(self, signum, frame):
    # Exit the class properly
    print("Stopping Jarvis Facebook Messenger server.")
    self.logout()
    sys.exit(0)

  def onMessage(self, author_id, message, thread_id, thread_type, **kwargs):
    # If the author is not this class, send request to Jarvis...
    if str(author_id) != str(self.uid):
      # Mark message as delivered
      self.markAsDelivered(author_id, thread_id)

      # Mark message as read
      self.markAsRead(author_id)

      # Be sure that the author is allowed
      if not self.allowAll:
        if not (str(author_id) in self.allowedIdList):
          self.sendMessage("You don't have right to speak to Jarvis! (Your ID is {})".format(str(author_id)), thread_id=thread_id, thread_type=thread_type)
          logging.warning("Not allowed user '{}' tried to speak to Jarvis.".format(str(author_id)))
          return

      # Be sure to have a normalized string to send to Jarvis
      message = unicodedata.normalize('NFKD', message).encode('ascii','ignore').decode('utf-8')

      logging.debug("Received message from '{}': '{}'.".format(str(author_id), str(message)))

      # Send request to Jarvis and receive answer
      response = self.executeOrder(str(message))
      logging.debug("Response from Jarvis: '{}'.".format(str(response)))

      # ... and respond to user with Jarvis response
      try:
        # Prepare the Jarvis response to the sender
        response_to_send = ""
        for json_dict in list(response):
          for key, value in json_dict.items():
            if response_to_send != "":
              response_to_send += "\n"

            if self.verbose_mode:
              response_to_send += "{}: {}".format(str(key), str(value))
            else:
              if (str(key) == 'answer') or (str(key) == 'info') or (str(key) == 'debug'):
                response_to_send += str(value)

        # Send Jarvis response to the sender
        if response_to_send != "":
          self.sendMessage(str(response_to_send), thread_id=thread_id, thread_type=thread_type)
      except ValueError:
        self.sendMessage("Can't parse Jarvis response: '{}'".format(str(response)), thread_id=thread_id, thread_type=thread_type)

      # Send the ID of the caller to himself if requested
      if self.getId:
        self.sendMessage("Your ID is '{}'".format(str(author_id)), thread_id=thread_id, thread_type=thread_type)

if __name__ == "__main__":
  # Define lambda function to convert string to bool
  def __str2bool(value):
    if value.lower() in ('yes', 'true', 't', 'y', '1'):
      return True
    if value.lower() in ('no', 'false', 'f', 'n', '0'):
      return False
    else:
      raise argparse.ArgumentTypeError('Boolean value expected.')

  # Parse received parameters
  parser = argparse.ArgumentParser(description='Jarvis Facebook Messenger Server')
  parser.add_argument('-e', '--email', help='Facebook email used as username')
  parser.add_argument('-p', '--password', help='Facebook password')
  parser.add_argument('-v', '--verbose', type=__str2bool, nargs='?', default="True", help='Show debug information (default: True)')
  parser.add_argument('-m', '--mute', type=__str2bool, nargs='?', default="True", help='Mute Jarvis (default: True)')
  parser.add_argument('-i', '--getId', type=__str2bool, nargs='?', default="False", help='Get ID of the sender (default: False)')
  parser.add_argument('-a', '--allowAll', type=__str2bool, nargs='?', default="True", help='Allow all people to send request to Jarvis with messenger (default: True)')
  parser.add_argument('-l', '--allowedIdList', default="[]", help='Allowed list of IDs to send request to Jarvis (default: [])')
  args = parser.parse_args()

  # Show more information if in debug mode
  if args.verbose:
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

  while True:
    # Create a Jarvis-Facebook messenger server instance
    jarvis_fb_server = JarvisFacebookMessengerServer(email = args.email,
                                                     password = args.password,
                                                     verbose = args.verbose,
                                                     mute = args.mute,
                                                     getId = args.getId,
                                                     allowAll = args.allowAll,
                                                     allowedIdList = ast.literal_eval(args.allowedIdList))
    # Add signals catching to quit application when jarvis ends
    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
      signal.signal(sig, jarvis_fb_server.properExit)

    try:
      # Listen facebook messenger message forever (until jarvis ends)
      jarvis_fb_server.listen()
    except KeyboardInterrupt:
      pass
    except Exception as e:
      # Restart Facebook Server in case an error occurs
      logging.warning("Facebook Messenger server crashed. Restarting...")
      try:
        logging.error(e.message)
      except Exception:
        pass
      jarvis_fb_server.stop_listening()
      jarvis_fb_server.logout()
      del jarvis_fb_server
