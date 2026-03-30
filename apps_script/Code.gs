/**
 * Daily Digest — Gmail sender
 *
 * Deploy as a Web App:
 *   Execute as: Me
 *   Who has access: Anyone
 *
 * The deployed URL goes in your .env as APPS_SCRIPT_URL.
 * Set SECRET_TOKEN below to the same value as APPS_SCRIPT_SECRET in your .env.
 */

var SECRET_TOKEN = "replace-with-your-own-random-secret";
var RECIPIENT   = "lynn.chiam@gmail.com";

function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);

    if (payload.token !== SECRET_TOKEN) {
      return json({ status: "error", message: "Unauthorized" }, 401);
    }

    var subject  = payload.subject  || "Daily Digest";
    var htmlBody = payload.html_body || "";

    GmailApp.sendEmail(RECIPIENT, subject, "", { htmlBody: htmlBody });

    return json({ status: "sent" });

  } catch (err) {
    return json({ status: "error", message: err.toString() });
  }
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
