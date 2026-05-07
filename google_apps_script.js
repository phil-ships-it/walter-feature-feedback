// Frag Walter — Logger
// Setup:
// 1. Neues Google Sheet öffnen
// 2. Erweiterungen → Apps Script
// 3. Diesen Code einfügen und speichern
// 4. Bereitstellen → Neue Bereitstellung → Web-App
//    - Ausführen als: Ich (deine Google-Adresse)
//    - Zugriff: Jeder
// 5. URL kopieren → in server.py als GOOGLE_WEBHOOK_URL eintragen

function doPost(e) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

    // Header-Zeile beim ersten Eintrag
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['Zeitstempel', 'Produkt-URL', 'Feature-Request', 'Walters Antwort', 'Bild-URL']);
      sheet.getRange(1, 1, 1, 5).setFontWeight('bold');
    }

    const data = JSON.parse(e.postData.contents);

    sheet.appendRow([
      new Date(),
      data.productUrl  || '',
      data.feature     || '',
      data.response    || '',
      data.imageUrl    || ''
    ]);

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Zum Testen im Browser
function doGet() {
  return ContentService.createTextOutput('Walter Logger läuft.');
}
