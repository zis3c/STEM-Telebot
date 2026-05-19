/**
 * Google Apps Script for STEM Bot Automation
 * 
 * INSTRUCTIONS:
 * 1. Open your Google Sheet.
 * 2. Go to Extensions > Apps Script.
 * 3. Delete any existing code and paste this entire script.
 * 4. Save the project (Cmd+S or Ctrl+S).
 * 5. Run the 'setupTrigger' function once to authorize and set up the automation.
 *    - Click 'Run' > 'setupTrigger'.
 *    - Grant permissions if asked.
 */

// --- CONFIGURATION ---
var SHEET_NAME = "STEM DB"; // Updated to match user's actual sheet name

// Column Indices (1-based for getRange, but 0-based for array access usually)
// A=1, B=2, ...
// A=1, B=2, ...
var COL_TIMESTAMP = 1;      // A
var COL_PERSONAL_EMAIL = 2; // B (User's Personal Email)
var COL_MATRIC = 4;         // D
var COL_USAS_EMAIL = 9;     // I
var COL_DATE_ENTRY = 14;    // N
var COL_MEMBERSHIP = 16;    // P
var COL_STATUS = 18;        // R
var COL_RECEIPT_URL = 19;   // S (Payment Receipt)
var COL_INVOICE_NO = 20;    // T (Invoice No)

var FEE_AMOUNT = "RM10.00"; // Fixed Fee
var EMAIL_ATTACH_PDF = true; // Send PDF as attachment
var EMAIL_INCLUDE_DRIVE_LINK = false; // Include Drive button in email body
var ADMIN_WEBHOOK_TOKEN = PropertiesService.getScriptProperties().getProperty("ADMIN_WEBHOOK_TOKEN");

// Secrets managed via Script Properties (File > Project Properties > Script Properties)
// Or run the 'setupSecrets' function once below.
var RECEIPT_FOLDER_ID = PropertiesService.getScriptProperties().getProperty("RECEIPT_FOLDER_ID");
var LOGO_FILE_ID = PropertiesService.getScriptProperties().getProperty("LOGO_FILE_ID");

var SAFE_NAME_RE = /^[A-Z0-9 .,'()\/-]{2,80}$/;
var SAFE_MATRIC_RE = /^[A-Z0-9]{6,15}$/;
var SAFE_EMAIL_RE = /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,189}\.[A-Za-z]{2,}$/;

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function sanitizeText(value, maxLen) {
    var clean = String(value || "")
        .replace(/[\u0000-\u001F\u007F]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    if (clean.length > maxLen) clean = clean.slice(0, maxLen);
    if (/^[=+\-@]/.test(clean)) clean = "'" + clean;
    return clean;
}

function sanitizeName(value) {
    return sanitizeText(value, 80).toUpperCase();
}

function sanitizeMatric(value) {
    return sanitizeText(value, 15).replace(/[^A-Za-z0-9]/g, "").toUpperCase();
}

function sanitizeInvoice(value) {
    return sanitizeText(value, 24).replace(/[^A-Za-z0-9\-]/g, "");
}

function isSafeName(name) {
    return SAFE_NAME_RE.test(name);
}

function isSafeMatric(matric) {
    return SAFE_MATRIC_RE.test(matric);
}

function isSafeEmail(email) {
    return SAFE_EMAIL_RE.test(email);
}

function sanitizeDriveUrl(url) {
    var val = String(url || "").trim();
    if (/^https:\/\/drive\.google\.com\/[A-Za-z0-9._~:/?#[\]@!$&'()*+,;=%-]+$/.test(val)) {
        return val;
    }
    return "";
}

/**
 * ONE-TIME SETUP: Run this function once to save your secrets.
 * Then delete the specific values from this code if sharing.
 */
function setupSecrets() {
    var props = PropertiesService.getScriptProperties();
    props.setProperties({
        "RECEIPT_FOLDER_ID": "PASTE_YOUR_FOLDER_ID_HERE",
        "LOGO_FILE_ID": "PASTE_YOUR_LOGO_ID_HERE",
        "ADMIN_WEBHOOK_TOKEN": "PASTE_RANDOM_LONG_SECRET_HERE"
    });
    Logger.log("Secrets saved successfully! You can now remove them from this function.");
}

/**
 * DEBUG CONFIGURATION
 * Run this to check if your secrets are saved correctly.
 */
function debugConfiguration() {
    var props = PropertiesService.getScriptProperties();
    var folderId = props.getProperty("RECEIPT_FOLDER_ID");
    var logoId = props.getProperty("LOGO_FILE_ID");

    Logger.log("--- CONFIG CHECK ---");
    Logger.log("Folder ID: " + (folderId ? "âœ… Found (" + folderId + ")" : "âŒ MISSING"));
    Logger.log("Logo ID:   " + (logoId ? "âœ… Found (" + logoId + ")" : "âŒ MISSING"));

    if (logoId) {
        var b64 = getEncodedLogo(logoId);
        Logger.log("Logo Fetch Test: " + (b64 ? "âœ… Success (Length: " + b64.length + ")" : "âŒ Failed to fetch/encode"));
    }
    Logger.log("--------------------");
}

/**
 * Helper: Fetch Image from Drive and convert to Base64 for embedding
 */
function getEncodedLogo(fileId) {
    if (!fileId || fileId === "PASTE_YOUR_LOGO_ID_HERE") {
        Logger.log("âš ï¸ Logo File ID is missing or placeholder.");
        return null;
    }
    try {
        var file = DriveApp.getFileById(fileId);
        var blob = file.getBlob();
        var b64 = Utilities.base64Encode(blob.getBytes());
        Logger.log("âœ… Logo encoded successfully. Size: " + b64.length);
        return "data:" + blob.getContentType() + ";base64," + b64;
    } catch (e) {
        Logger.log("âš ï¸ Could not fetch logo: " + e.toString());
        return null;
    }
}

/**
 * Triggered automatically on form submit.
 * Uses the event object (e) to get the row efficiently.
 */
function onFormSubmit(e) {
    if (!e) {
        Logger.log("âš ï¸ You are running this manually. 'e' is undefined. Running testLastRow() instead.");
        testLastRow();
        return;
    }

    // Valid event. Use the sheet where the submission happened.
    var sheet = e.range.getSheet();
    var row = e.range.getRow();
    if (sheet.getName() !== SHEET_NAME) {
        Logger.log("Ã¢Å¡Â Ã¯Â¸Â Ignored submit from unexpected sheet: " + sheet.getName());
        return;
    }

    Logger.log("Form Submitted on Sheet: " + sheet.getName() + ", Row: " + row);
    processRowOnSubmit(sheet, row);
}

/**
 * Manual testing function. Processes the last row.
 */
function testLastRow() {
    var sheet = getTargetSheet();
    if (!sheet) {
        Logger.log("âŒ CRITICAL: Could not find any sheet.");
        return;
    }

    var lastRow = sheet.getLastRow();
    Logger.log("Testing Last Row: " + lastRow + " on sheet '" + sheet.getName() + "'");
    processRowOnSubmit(sheet, lastRow);
}

/**
 * SIMPLE EMAIL TEST
 * Run this function to test email sending to YOURSELF with dummy data.
 */
function testSimpleEmail() {
    var email = Session.getActiveUser().getEmail(); // Auto-detects your email
    var name = "Test User";
    var matric = "TEST123456";
    var memberId = "STEM(24/25)9999";
    var date = "31/12/25";
    var invoiceNo = "INV-TEST999";

    Logger.log("ðŸ§ª Running Simple Email Test...");
    sendReceiptEmail(email, name, matric, memberId, date, invoiceNo);
}

/**
 * Helper to get the correct sheet safely
 */
function getTargetSheet() {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
        // Fallback: Get the first sheet (usually 'Form Responses 1')
        sheet = ss.getSheets()[0];
        Logger.log("âš ï¸ Sheet '" + SHEET_NAME + "' not found. Fallback to first sheet: '" + sheet.getName() + "'");
    }
    return sheet;
}

/**
 * Main Logic to populate columns and Send Email
 */
function processRowOnSubmit(sheet, rowIdx) {
    // Prevent duplicate sends when two triggers process the same row at the same time.
    var lock = LockService.getDocumentLock();
    lock.waitLock(30000);
    try {
        var dataRange = sheet.getRange(rowIdx, 1, 1, 21); // Read cols A to U
        var values = dataRange.getValues()[0];

        // DEBUG LOG
        // Logger.log("Row " + rowIdx + " Dump: " + JSON.stringify(values));

        // 1. Get Timestamp (Col A) - Index 0
        var timestamp = values[0];
        if (!timestamp || timestamp === "") {
            Logger.log("âš ï¸ Row " + rowIdx + " SKIPPED. Reason: Timestamp (Col A) is empty.");
            return;
        }

        var dateObj = new Date(timestamp);

        // 2. Automate Date of Entry (Col N) - Index 13
        var dateEntry = Utilities.formatDate(dateObj, Session.getScriptTimeZone(), "dd/MM/yy");

        // 3. Sanitize/validate key user input from Google Form.
        var matricRaw = String(values[3]).trim();
        var matric = sanitizeMatric(matricRaw);
        var nameRaw = String(values[2]).trim();
        var name = sanitizeName(nameRaw);
        var personalEmailRaw = String(values[COL_PERSONAL_EMAIL - 1]).trim();
        var personalEmail = sanitizeText(personalEmailRaw, 254);

        if (!isSafeMatric(matric) || !isSafeName(name) || !isSafeEmail(personalEmail)) {
            Logger.log("Row " + rowIdx + " rejected due to unsafe input.");
            sheet.getRange(rowIdx, COL_STATUS).setValue("Rejected - Invalid Input");
            return;
        }

        // 3b. Build derived USAS email from validated matric only.
        var usasEmail = matric + "@student.usas.edu.my";

        // --- WRITE UPDATES ---
        // Update Name (3), Matric (4), Email (9), Date (14)

        // Capitalize Name & Matric in place if needed
        if (name !== nameRaw) sheet.getRange(rowIdx, 3).setValue(name);
        if (matric !== matricRaw) sheet.getRange(rowIdx, COL_MATRIC).setValue(matric);

        sheet.getRange(rowIdx, COL_USAS_EMAIL).setValue(usasEmail);
        sheet.getRange(rowIdx, COL_DATE_ENTRY).setValue(dateEntry);

        // Stop auto-send on submit. Wait for admin approval path.
        sheet.getRange(rowIdx, COL_STATUS).setValue("Pending");

        // --- FORMATTING (User Request) ---
        // Right Align, Inter Font, Size 10, All Borders
        var fullRowRange = sheet.getRange(rowIdx, 1, 1, 21); // Columns A to U
        fullRowRange
            .setHorizontalAlignment("right")
            .setVerticalAlignment("middle") // Good practice
            .setFontFamily("Inter")
            .setFontSize(10)
            .setBorder(true, true, true, true, true, true, "#000000", SpreadsheetApp.BorderStyle.SOLID);
    } finally {
        lock.releaseLock();
    }
}

/**
 * Admin approval path only.
 * Call when Telegram admin accepts student.
 */
function approveStudentAndSendReceipt(rowIdx) {
    var sheet = getTargetSheet();
    if (!sheet) return { ok: false, error: "Sheet not found" };

    var row = parseInt(rowIdx, 10);
    if (!row || row < 2) return { ok: false, error: "Invalid row index" };

    var lock = LockService.getDocumentLock();
    lock.waitLock(30000);
    try {
        var rowRange = sheet.getRange(row, 1, 1, 21);
        var values = rowRange.getValues()[0];
        var timestamp = values[0];
        var name = sanitizeName(values[2]);
        var matric = sanitizeMatric(values[3]);
        var personalEmail = sanitizeText(values[COL_PERSONAL_EMAIL - 1], 254);
        var memberId = sanitizeText(values[COL_MEMBERSHIP - 1], 32);
        var invoiceNo = sanitizeInvoice(values[COL_INVOICE_NO - 1]);
        var dateEntry = sanitizeText(values[COL_DATE_ENTRY - 1], 20);
        var receiptUrl = sanitizeDriveUrl(values[COL_RECEIPT_URL - 1]);

        if (!timestamp || !isSafeName(name) || !isSafeMatric(matric) || !isSafeEmail(personalEmail)) {
            values[COL_STATUS - 1] = "Rejected - Invalid Input";
            rowRange.setValues([values]);
            return { ok: false, error: "Invalid student data" };
        }

        if (!memberId) {
            memberId = generateMembershipId(sheet, new Date(timestamp), row);
            values[COL_MEMBERSHIP - 1] = memberId;
        }
        if (!invoiceNo) {
            invoiceNo = "INV-" + Math.floor(100000 + Math.random() * 900000);
            values[COL_INVOICE_NO - 1] = invoiceNo;
        }
        if (!dateEntry) {
            dateEntry = Utilities.formatDate(new Date(timestamp), Session.getScriptTimeZone(), "dd/MM/yy");
            values[COL_DATE_ENTRY - 1] = dateEntry;
        }

        if (receiptUrl) {
            values[COL_STATUS - 1] = "Approved";
            rowRange.setValues([values]);
            return { ok: true, row: row, message: "Receipt already exists" };
        }

        values[COL_RECEIPT_URL - 1] = "SENDING_" + new Date().toISOString();
        values[COL_STATUS - 1] = "Pending Email Dispatch";
        rowRange.setValues([values]);

        var newReceiptUrl = sendReceiptEmail(personalEmail, name, matric, memberId, dateEntry, invoiceNo);
        if (!newReceiptUrl) {
            values[COL_RECEIPT_URL - 1] = "";
            values[COL_STATUS - 1] = "Approved";
            rowRange.setValues([values]);
            return { ok: false, error: "Receipt send failed" };
        }

        values[COL_RECEIPT_URL - 1] = newReceiptUrl;
        values[COL_STATUS - 1] = "Approved";
        rowRange.setValues([values]);
        return { ok: true, row: row, receiptUrl: newReceiptUrl };
    } finally {
        lock.releaseLock();
    }
}

/**
 * Admin reject path.
 * Deletes row from sheet so rejected student has no DB record and no invoice.
 */
function rejectStudentAndDeleteRow(rowIdx) {
    var sheet = getTargetSheet();
    if (!sheet) return { ok: false, error: "Sheet not found" };

    var row = parseInt(rowIdx, 10);
    if (!row || row < 2) return { ok: false, error: "Invalid row index" };

    var lock = LockService.getDocumentLock();
    lock.waitLock(30000);
    try {
        var lastRow = sheet.getLastRow();
        if (row > lastRow) return { ok: false, error: "Row not found" };
        sheet.deleteRow(row);
        return { ok: true, row: row, message: "Rejected and deleted" };
    } finally {
        lock.releaseLock();
    }
}

/**
 * Webhook endpoint for Telegram/admin system.
 * Payload: {"token":"<ADMIN_WEBHOOK_TOKEN>","action":"approve","row":12}
 */
function doPost(e) {
    try {
        var body = JSON.parse(e.postData.contents || "{}");
        if (!ADMIN_WEBHOOK_TOKEN || body.token !== ADMIN_WEBHOOK_TOKEN) {
            return ContentService
                .createTextOutput(JSON.stringify({ ok: false, error: "Unauthorized" }))
                .setMimeType(ContentService.MimeType.JSON);
        }
        if (body.action === "approve") {
            var result = approveStudentAndSendReceipt(body.row);
            return ContentService
                .createTextOutput(JSON.stringify(result))
                .setMimeType(ContentService.MimeType.JSON);
        }
        if (body.action === "reject") {
            var rejectResult = rejectStudentAndDeleteRow(body.row);
            return ContentService
                .createTextOutput(JSON.stringify(rejectResult))
                .setMimeType(ContentService.MimeType.JSON);
        }
        if (body.action !== "approve" && body.action !== "reject") {
            return ContentService
                .createTextOutput(JSON.stringify({ ok: false, error: "Unknown action" }))
                .setMimeType(ContentService.MimeType.JSON);
        }
    } catch (err) {
        return ContentService
            .createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
            .setMimeType(ContentService.MimeType.JSON);
    }
}
/**
 * Generates and Sends the HTML Receipt Email with PDF Attachment + Download Link
 * Returns the download URL
 */
function sendReceiptEmail(email, name, matric, memberId, date, invoiceNo) {
    try {
        if (!isSafeEmail(email) || !isSafeMatric(matric) || !isSafeName(name)) {
            Logger.log("âŒ Refused receipt send due to invalid/suspicious fields.");
            return null;
        }

        memberId = sanitizeText(memberId, 32);
        invoiceNo = sanitizeInvoice(invoiceNo);
        date = sanitizeText(date, 20);

        var receiptNo = memberId; // Use MemberID for easy tracking
        var fileName = "STEM_Receipt_" + memberId + ".pdf";

        // 0. Fetch Logo (if configured)
        var logoBase64 = getEncodedLogo(LOGO_FILE_ID);

        // 1. Generate HTML for PDF Attachment (Table/Formal Style)
        var pdfHtml = createPdfHtml(name, matric, memberId, date, invoiceNo, receiptNo, logoBase64);
        var pdfBlob = Utilities.newBlob(pdfHtml, "text/html", "Receipt-" + memberId + ".html").getAs("application/pdf");
        pdfBlob.setName(fileName);

        // 2. Save PDF to Google Drive & Get Download Link
        var file;
        try {
            if (RECEIPT_FOLDER_ID && RECEIPT_FOLDER_ID !== "PASTE_YOUR_FOLDER_ID_HERE") {
                var folder = DriveApp.getFolderById(RECEIPT_FOLDER_ID);
                file = folder.createFile(pdfBlob);
                Logger.log("ðŸ“‚ Saved to Folder: " + folder.getName());
            } else {
                throw new Error("Folder ID not set.");
            }
        } catch (e) {
            Logger.log("âš ï¸ Saving to Root (Folder ID missing/invalid).");
            file = DriveApp.createFile(pdfBlob);
        }

        // Keep receipt private by default.
        file.setSharing(DriveApp.Access.PRIVATE, DriveApp.Permission.VIEW);
        var downloadUrl = file.getUrl();

        // 3. Generate HTML for Email Body (Card Style)
        var linkForEmail = EMAIL_INCLUDE_DRIVE_LINK ? downloadUrl : "";
        var emailHtml = createEmailHtml(name, matric, memberId, date, invoiceNo, receiptNo, linkForEmail);

        var mailOptions = {
            to: email,
            subject: "Payment Receipt - STEM Membership",
            htmlBody: emailHtml
        };
        if (EMAIL_ATTACH_PDF) {
            mailOptions.attachments = [pdfBlob];
        }
        MailApp.sendEmail(mailOptions);

        // Optional: Clean up file from Drive if you don't want to save a copy
        // file.setTrashed(true); // Uncomment to delete after sending

        Logger.log("âœ… Receipt sent to: " + email);
        return downloadUrl; // Return URL to save to Sheet
    } catch (e) {
        Logger.log("âŒ Failed to send email: " + e.toString());
        return null;
    }
}

/**
 * Helper: Fetch Image from Drive and convert to Base64 for embedding
 */
function getEncodedLogo(fileId) {
    if (!fileId || fileId === "PASTE_YOUR_LOGO_ID_HERE") return null;
    try {
        var file = DriveApp.getFileById(fileId);
        var blob = file.getBlob();
        var b64 = Utilities.base64Encode(blob.getBytes());
        return "data:" + blob.getContentType() + ";base64," + b64;
    } catch (e) {
        Logger.log("âš ï¸ Could not fetch logo: " + e.toString());
        return null;
    }
}

/**
 * EMAIL BODY HTML (Card Style)
 */
/**
 * EMAIL BODY HTML (Card Style)
 */
function createEmailHtml(name, matric, memberId, date, invoiceNo, receiptNo, downloadUrl) {
    var bgBody = "#f5f5f7";
    var bgCard = "#ffffff";
    var textHeader = "#1d1d1f";
    var textLabel = "#86868b";
    var textValue = "#1d1d1f";
    var accentColor = "#012951";
    var highlightColor = "#f7c525";
    var safeName = escapeHtml(name);
    var safeMatric = escapeHtml(matric);
    var safeDate = escapeHtml(date);
    var safeReceiptNo = escapeHtml(receiptNo);
    var safeInvoiceNo = escapeHtml(invoiceNo);
    var safeDownloadUrl = sanitizeDriveUrl(downloadUrl);
    var downloadButton = safeDownloadUrl
        ? `<div style="text-align: center; margin-top: 30px;"><a href="${safeDownloadUrl}" class="btn-download" target="_blank" rel="noopener noreferrer">Open Receipt in Drive</a></div>`
        : `<div style="text-align: center; margin-top: 30px; color: ${textLabel}; font-size: 13px;">Your signed PDF receipt is attached to this email.</div>`;

    return `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
             @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
            body { margin: 0; padding: 0; background-color: ${bgBody}; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
            .container { max-width: 600px; margin: 40px auto; background: ${bgCard}; border-radius: 18px; overflow: hidden; }
            .content { padding: 40px; }
            .header { text-align: center; margin-bottom: 30px; }
            .logo { font-size: 24px; font-weight: 700; color: ${textHeader}; }
            .logo span { color: ${highlightColor}; }
            .btn-download { display: inline-block; margin-top: 20px; padding: 12px 24px; background-color: ${accentColor}; color: white !important; text-decoration: none; border-radius: 980px; font-size: 14px; font-weight: 600; }
            
            /* Mobile Responsiveness */
            @media only screen and (max-width: 480px) {
                .container { margin: 0 auto; border-radius: 0; width: 100% !important; }
                .content { padding: 24px !important; }
                .logo { font-size: 20px !important; }
                .amount-large { font-size: 32px !important; }
                .detail-text { font-size: 13px !important; }
            }
        </style>
    </head>
    <body>
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: ${bgBody};">
            <tr>
                <td align="center" style="padding: 20px;">
                    <div class="container">
                        <div class="content">
                            <div class="header">
                                <div class="logo">STEM <span>USAS</span></div>
                                <div style="font-size: 14px; color: ${textLabel}; margin-top: 5px;">Payment Received</div>
                            </div>

                            <div style="text-align: center; color: ${textHeader}; margin-bottom: 30px;">
                                Hi <b>${safeName}</b>,<br>
                                <span style="font-size: 14px; color: ${textLabel};">Thank you regarding your membership payment.</span>
                            </div>

                            <div style="text-align: center; margin-bottom: 30px;">
                                <div class="amount-large" style="font-size: 42px; font-weight: 700; color: ${textHeader};">${FEE_AMOUNT}</div>
                                <div style="font-size: 13px; color: ${textLabel};">Paid on ${safeDate}</div>
                            </div>

                            <!-- Key Details for Email -->
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; color: ${textLabel}; font-size: 14px;">Date</td>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; text-align: right; font-weight: 600; color: ${textValue}; font-size: 14px;">${safeDate}</td>
                                </tr>
                                <tr>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; color: ${textLabel}; font-size: 14px;">Membership ID</td>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; text-align: right; font-weight: 600; color: ${textValue}; font-size: 14px;">${safeReceiptNo}</td>
                                </tr>
                                <tr>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; color: ${textLabel}; font-size: 14px;">Invoice ID</td>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; text-align: right; font-weight: 600; color: ${textValue}; font-size: 14px;">${safeInvoiceNo}</td>
                                </tr>
                                <tr>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; color: ${textLabel}; font-size: 14px;">Matric No</td>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; text-align: right; font-weight: 600; color: ${textValue}; font-size: 14px;">${safeMatric}</td>
                                </tr>
                                <tr>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; color: ${textLabel}; font-size: 14px;">Item</td>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; text-align: right; font-weight: 600; color: ${textValue}; font-size: 14px; word-break: break-word; max-width: 150px;">STEM Membership</td>
                                </tr>
                                <tr>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; color: ${textLabel}; font-size: 14px;">Status</td>
                                    <td class="detail-text" style="padding: 12px 0; border-bottom: 1px solid #eeeeee; text-align: right; font-weight: 600; color: #34c759; font-size: 14px;">Paid</td>
                                </tr>
                            </table>

                             ${downloadButton}
                        </div>
                         <div style="background-color: #fafafa; padding: 20px; text-align: center; font-size: 12px; color: ${textLabel};">
                            STEM USAS
                        </div>
                    </div>
                </td>
            </tr>
        </table>
    </body>
    </html>
    `;
}

/**
 * PDF HTML (Table Style)
 * Formal, Invoice-like structure with the grid table.
 */
function createPdfHtml(name, matric, memberId, date, invoiceNo, receiptNo, logoBase64) {
    var bgBody = "#ffffff"; // White background for PDF
    var textHeader = "#1d1d1f";
    var textLabel = "#86868b";
    var textValue = "#1d1d1f";
    var accentColor = "#012951";
    var highlightColor = "#1d1d1f";
    var safeName = escapeHtml(name);
    var safeMatric = escapeHtml(matric);
    var safeDate = escapeHtml(date);
    var safeReceiptNo = escapeHtml(receiptNo);
    var safeInvoiceNo = escapeHtml(invoiceNo);

    // Logo Logic
    var logoHtml = logoBase64
        ? `<img src="${logoBase64}" style="height: 80px; width: auto; vertical-align: middle;">`
        : `<span class="logo">STEM <span>USAS</span></span>`;

    return `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
            body { margin: 0; padding: 40px; background-color: ${bgBody}; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
            .header { margin-bottom: 40px; border-bottom: 2px solid ${accentColor}; padding-bottom: 20px; }
            .logo { font-size: 28px; font-weight: 700; color: ${textHeader}; }
            .logo span { color: ${highlightColor}; }
            .title { font-size: 16px; font-weight: 600; color: ${textLabel}; text-transform: uppercase; float: right; margin-top: 10px; }
            
            .meta-table { width: 100%; margin-bottom: 40px; }
            .meta-table td { padding: 5px 0; vertical-align: top; }
            .meta-label { font-size: 12px; color: ${textLabel}; font-weight: 600; text-transform: uppercase; }
            .meta-value { font-size: 14px; color: ${textValue}; font-weight: 500; }

            .bill-to { margin-bottom: 40px; } 
            .bill-label { font-size: 12px; color: ${textLabel}; font-weight: 600; text-transform: uppercase; margin-bottom: 25px; } /* Wide spacing */
            .bill-name { font-size: 18px; font-weight: 700; color: ${textHeader}; margin-bottom: 2px; line-height: 1.2; } /* Tight spacing */
            
            /* The Grid Table */
            .main-table { width: 100%; border-collapse: separate; border-spacing: 0; border: 1px solid #e5e5e5; border-radius: 8px; overflow: hidden; }
            .main-table th { text-align: left; padding: 12px 16px; background-color: #fafafa; color: ${textLabel}; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #e5e5e5; }
            .main-table td { padding: 16px; border-bottom: 1px solid #e5e5e5; font-size: 14px; color: ${textValue}; }
            .main-table tr:last-child td { border-bottom: none; }
            .total-row td { font-weight: 700; background-color: #fbfffe; }
            .total-val { color: ${accentColor}; }

            .terms-box { margin-top: 15px; width: 100%; box-sizing: border-box; background: #f9f9f9; padding: 20px; border-radius: 8px; font-size: 11px; color: #666; line-height: 1.6; border: 1px solid #eee; }

            .footer { margin-top: 30px; text-align: center; font-size: 10px; color: ${textLabel}; }
        </style>
    </head>
    <body>
        <div class="header">
            ${logoHtml}
            <span class="title">Official Receipt STEM USAS</span>
        </div>

        <table width="100%">
            <tr>
                <td width="60%" style="vertical-align: top;">
                    <div class="bill-to">
                        <div class="bill-label">Billed To</div>
                        <div class="bill-name">${safeName}</div>
                        <div class="meta-value">${safeMatric}</div>
                    </div>
                </td>
                <td width="40%" align="right" style="vertical-align: top;">
                    <table class="meta-table" style="text-align: right; border-collapse: collapse;">
                        <tr>
                            <td class="meta-label" style="padding-bottom: 2px;">Date</td>
                        </tr>
                        <tr>
                             <td class="meta-value" style="padding-bottom: 20px;">${safeDate}</td>
                        </tr>
                        <tr>
                            <td class="meta-label" style="padding-bottom: 2px;">Membership ID</td>
                        </tr>
                        <tr>
                             <td class="meta-value" style="padding-bottom: 20px;">${safeReceiptNo}</td>
                        </tr>
                        <tr>
                            <td class="meta-label" style="padding-bottom: 2px;">Invoice</td>
                        </tr>
                         <tr>
                             <td class="meta-value">${safeInvoiceNo}</td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Tablet Itemization -->
        <table class="main-table">
            <thead>
                <tr>
                    <th width="70%">Description</th>
                    <th width="30%" style="text-align: right;">Amount</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>
                        <b>STEM Membership Registration</b><br>
                        <span style="font-size: 12px; color: #888;">One-time registration fee for STEM Societies USAS</span>
                    </td>
                    <td style="text-align: right; font-weight: 600;">${FEE_AMOUNT}</td>
                </tr>
                <tr class="total-row">
                    <td style="text-align: right;">TOTAL</td>
                    <td style="text-align: right;" class="total-val">${FEE_AMOUNT}</td>
                </tr>
            </tbody>
        </table>

         <!-- Bottom Section: Privileges Box -->
        <div class="terms-box">
            <b style="color: #1d1d1f; text-transform: uppercase;">Membership Privileges</b><br>
            â€¢ Priority Event Access guarantees early registration and secured spots for all STEM USAS workshops and events.<br>
            â€¢ AGM Voting Rights grant the power to elect leadership and influence association policies.<br>
            â€¢ Exclusive Perks include access to limited-edition merchandise and special discounts on paid programs.<br>
        </div>

        <div class="terms-box" style="margin-top: 15px;">
            <b style="color: #1d1d1f; text-transform: uppercase;">Check Your Status</b><br>
            Join our Official Telegram Bot to verify your eligibility and access your digital ID card.<br>
            ðŸ”— <b>Link:</b> <a href="https://t.me/stemusasbot" style="color: #012951; text-decoration: none;">https://t.me/stemusasbot</a>
        </div>

        <div class="terms-box" style="margin-top: 15px; border-left: 4px solid #f7c525;">
            <b style="color: #1d1d1f; text-transform: uppercase;">Membership Regulation</b><br>
            Please note that under HEP USAS regulations, student membership is valid for one (1) academic session only. 
            <b>Members are required to renew their membership annually</b> to maintain active status and privileges.
        </div>

        <div class="footer">
            STEM USAS â€¢ zis3c â€¢ Computer Generated Receipt
            <div style="margin-top: 15px; font-size: 9px; color: #aaa; line-height: 1.4; border-top: 1px solid #eee; padding-top: 10px;">
                <b>IMPORTANT:</b> Keep for records. Fraud/Falsification is a serious offense leading to disqualification and reporting to Student Affairs (HEP).
            </div>
        </div>
    </body>
    </html>
    `;
}

/**
 * BROADCAST: Process ALL rows to backfill data and send emails.
 * Run this MANUALLY to process migrated data.
 */
function broadcastAllRows() {
    var sheet = getTargetSheet();
    if (!sheet) return;

    var lastRow = sheet.getLastRow();
    // Start from Row 2 (Skip Header)
    for (var i = 2; i <= lastRow; i++) {
        Logger.log("ðŸ”„ Processing Row " + i + " of " + lastRow);
        processRowOnSubmit(sheet, i);
        // Small delay to prevent hitting Google rate limits (MailApp: ~100/day for free Gmail)
        Utilities.sleep(1000);
    }
    Logger.log("âœ… Broadcast Complete!");
}

/**
 * Generates the Membership ID
 */
function generateMembershipId(sheet, dateObj, currentRowIdx) {
    // 1. Calculate Session
    var year = dateObj.getFullYear();
    var month = dateObj.getMonth(); // 0-11
    var startYear, endYear;

    if (month >= 8) { // September onwards
        startYear = year;
        endYear = year + 1;
    } else {
        startYear = year - 1;
        endYear = year;
    }

    var yyStart = String(startYear).slice(-2);
    var yyEnd = String(endYear).slice(-2);
    var prefix = "STEM(" + yyStart + "/" + yyEnd + ")";

    // 2. Find Max ID with this prefix
    var lastRow = sheet.getLastRow();
    var maxSeq = 0;

    if (lastRow > 1) {
        var ids = sheet.getRange(2, COL_MEMBERSHIP, lastRow - 1, 1).getValues(); // Get all IDs
        for (var i = 0; i < ids.length; i++) {
            if ((i + 2) == currentRowIdx) continue;

            var val = String(ids[i][0]);
            if (val.startsWith(prefix)) {
                var remainder = val.replace(prefix, "");
                var seq = parseInt(remainder, 10);
                if (!isNaN(seq) && seq > maxSeq) maxSeq = seq;
            }
        }
    }

    // 3. Increment
    var newSeq = maxSeq + 1;
    return prefix + String(newSeq).padStart(4, '0');
}

/**
 * FORCE AUTHORIZATION
 * Run this function ONCE to force Google to ask for Email permissions.
 * Click 'Run' > 'forceAuth'
 */
function forceAuth() {
    Logger.log("Checking quota: " + MailApp.getRemainingDailyQuota());
    Logger.log("Checking User: " + Session.getEffectiveUser().getEmail());

    // Just by calling DriveApp here, we force Google to ask for Drive permissions too
    try {
        var root = DriveApp.getRootFolder();
        Logger.log("Drive Access Confirmed: " + root.getName());
    } catch (e) {
        Logger.log("Drive Access Needed");
    }

    setupTrigger(); // Re-run setup to be sure
}

/**
 * TRIGGER SETUP
 * Run this function ONCE manually.
 */
function setupTrigger() {
    var triggers = ScriptApp.getProjectTriggers();
    for (var i = 0; i < triggers.length; i++) {
        if (triggers[i].getEventType() === ScriptApp.EventType.ON_FORM_SUBMIT) {
            ScriptApp.deleteTrigger(triggers[i]);
        }
    }
    ScriptApp.newTrigger("onFormSubmit")
        .forSpreadsheet(SpreadsheetApp.getActive())
        .onFormSubmit()
        .create();

    Logger.log("Trigger set up successfully!");
}


