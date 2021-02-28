import argparse
import boto3
import json
import os
import sys
import urllib.request

if "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
   topic = os.environ["TOPIC"]
   client = boto3.client("sns")

class Availability:
   def __init__(self, config, debug=False):
      self.config = config
      self.debug = debug

   def get_availability(self, url, headers):
      request = urllib.request.Request(url)
      request.add_header("user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.192 Safari/537.36")
      for header in headers:
         request.add_header(header, headers[header])
      try:
         response = urllib.request.urlopen(request)
      except urllib.error.HTTPError as e:
         print(e)
         sys.exit(1)

      if response.status == 200:
         return json.loads(response.read().decode('utf-8'))
      else:
         sys.exit(1)

   def notify(self, notifications):
      if len(notifications["availability_at"]) == 0:
         message = "No vaccine availability at {}.".format(notifications["store"])
      else:
         subject = "Vaccination availability alert"
         message = ""
         for notification in notifications["availability_at"]:
            message += "Vaccine availability for {} at {}.\n".format(notification["store"], notification["location"])
         if "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
            client.publish(
               TopicArn=topic,
               Subject=subject,
               Message=message
            )
      print(message)
      return notifications

   def check_cvs(self, user):
      locations = []
      baseurl = self.config["cvs"]["url"]
      headers = self.config["cvs"]["headers"]
      response = self.get_availability(baseurl, headers)
      for store in response["responsePayloadData"]["data"]["NJ"]:
         if (store["status"] != "Fully Booked"): 
            locations.append(store["city"])
            print("(CVS) Vaccine availability at {}".format(store["city"]))
         elif self.debug:
            print("(CVS) No vaccine availability at {}".format(store["city"]))
      output = {
         "store": "CVS",
         "availability_at": locations
      }
      return output

   def check_riteaid(self, user):
      locations = []
      baseurl = self.config["riteaid"]["url"]
      headers = self.config["riteaid"]["headers"]
      for store in self.config["user_preferences"][user]["riteaid"]:
         url = "{}{}".format(baseurl, store)
         location = self.config["user_preferences"][user]["riteaid"][store]
         response = self.get_availability(url, headers)
         if (response["Data"]["slots"]["1"] or response["Data"]["slots"]["2"]):
            locations.append(location)
            print("(RiteAid) Vaccine availability at {}".format(location))
         elif self.debug:
            print("(RiteAid) No vaccine availability at {}".format(location))
      output = {
         "store": "RiteAid",
         "availability_at": locations
      }
      return output

def main():
   ap = argparse.ArgumentParser()
   ap.add_argument("--config", required=True, help="path to application configurations")
   ap.add_argument("--user", required=True, help="user from config.json")
   args = ap.parse_args()

   with open(args.config) as f:
      config = json.load(f)

   av = Availability(config)
   for user in [args.user]:
      print("Performing availability checks for {}.".format(user))
      av.notify(av.check_cvs(user))
      av.notify(av.check_riteaid(user))

if __name__ == "__main__":
   main()
