import smtplib

sender = input("Enter email address to send from: ")
password = input("Password: ")
reciever = input("Input reciever email: ")
subject = input("Subject: ")
body = input("Message: ")
message = "Subject:" & subject & "\ " & body

with smtplib.SMTP("smtp.gmail.com", 587) as smtpserver
  smtpserver.ehlo()
  smtpserver.starttls()
  smtpserver.ehlo()
  smtpserver.login(sender, password)
  smtpswerver.sendmail(sender, reciever, message)
  
print("Sent")
