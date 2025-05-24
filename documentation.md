# TejOCR - User Documentation

**Easy-to-use OCR (text recognition) for LibreOffice Writer**

---

## 🌟 **What is TejOCR?**

TejOCR is a simple add-on for LibreOffice Writer that can **read text from images** and **type it into your document automatically**. 

Think of it as having a smart assistant that can look at a picture with text (like a screenshot, photo of a page, or scanned document) and copy all the words into your document so you don't have to type them manually.

### **What it can do:**
- ✅ Read text from image files (PNG, JPEG, etc.)
- ✅ Read text from images already in your document  
- ✅ Automatically insert the recognized text where you want it
- ✅ Work with many different languages
- ✅ Handle different types of text (printed, handwritten, computer screenshots)

---

## 📋 **Before You Start**

### **System Requirements**
- **Computer**: Mac, Windows, or Linux
- **LibreOffice**: Version 4.0 or newer (free from [libreoffice.org](https://libreoffice.org))
- **Internet connection**: For initial setup only

### **What Gets Installed**
1. **TejOCR Extension**: The add-on that goes into LibreOffice
2. **Tesseract**: The "brain" that actually reads text from images
3. **Helper Programs**: Small programs that help everything work together

---

## 🚀 **Getting Started**

### **Step 1: Install Everything**

**Easiest Way (Recommended):**
1. Download the TejOCR extension file (ends with `.oxt`)
2. Run our automatic installer script: `python3 install_dependencies.py`
3. Install the extension in LibreOffice (see Step 2)

**Manual Way:**
```bash
# Install the text recognition engine
brew install tesseract  # Mac
sudo apt install tesseract-ocr  # Linux
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

# Install helper programs
/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/Current/bin/python3 -m pip install numpy pytesseract pillow
```

### **Step 2: Add TejOCR to LibreOffice**

1. **Open LibreOffice Writer**
2. **Go to Tools → Extension Manager**
3. **Click "Add..."**
4. **Select the TejOCR file** (ends with `.oxt`)
5. **Click "OK"**
6. **Restart LibreOffice completely**
7. **Look for "TejOCR" in the top menu** - you should see it!

### **Step 3: Check Everything is Working**

1. **In LibreOffice Writer, go to Tools → TejOCR → Settings**
2. **You should see green checkmarks (✅) next to:**
   - Tesseract (the text recognition engine)
   - Python packages (helper programs)
3. **If you see red X marks (❌)**, follow the error messages to fix them

---

## 📖 **How to Use TejOCR**

### **Method 1: Read Text from an Image File**

**When to use this:** You have an image saved on your computer (screenshot, photo, scanned document)

1. **Open LibreOffice Writer**
2. **Put your cursor where you want the text to appear** (click in your document)
3. **Go to Tools → TejOCR → OCR Image from File...**
4. **Select your image file**
5. **Wait a moment** - TejOCR will read the text and insert it automatically!

### **Method 2: Read Text from an Image Already in Your Document**

**When to use this:** You've already inserted an image into your document and want to extract text from it

1. **Click on the image** in your document (you should see selection handles around it)
2. **Go to Tools → TejOCR → OCR Selected Image**
3. **Wait a moment** - TejOCR will read the text and add it to your document!

---

## 💡 **Tips for Best Results**

### **Image Quality Matters**
- ✅ **Clear, crisp text** works best
- ✅ **Good contrast** (dark text on light background, or vice versa)
- ✅ **Straight, not tilted** images work better
- ✅ **Higher resolution** generally gives better results

### **Text Types That Work Well**
- ✅ **Printed text** (books, documents, websites)
- ✅ **Computer screenshots** (text from other programs)
- ✅ **Typed documents** (scanned papers)
- ⚠️ **Handwriting** (results may vary)
- ⚠️ **Very small text** (might be hard to read)

### **Languages**
- TejOCR can recognize many languages
- English works best by default
- Other languages may need additional setup

---

## 🔧 **Troubleshooting**

### **"TejOCR menu doesn't appear"**
- Make sure you restarted LibreOffice completely after installation
- Check Tools → Extension Manager to see if TejOCR is listed
- Try installing the extension again

### **"No text was found" or poor results**
- Make sure your image has clear, readable text
- Try a different image to test if TejOCR is working
- Check the image isn't too blurry or low resolution

### **"Dependencies missing" errors**
- Go to Tools → TejOCR → Settings to see what's missing
- Run the installer script again: `python3 install_dependencies.py`
- Follow the specific instructions in the error message

### **Text appears in the wrong place**
- Click where you want the text to appear before starting OCR
- The text will be inserted where your cursor is located

### **Need More Help?**
1. **Check Settings**: Tools → TejOCR → Settings shows what's working and what isn't
2. **Error Messages**: Read them carefully - they often tell you exactly what to do
3. **Try Simple Test**: Use a clear screenshot with large text to test if basic functionality works

---

## 🎯 **Common Uses**

### **For Students**
- Extract text from screenshots of online resources
- Convert photos of textbook pages to editable text
- Quickly copy text from PDF images

### **For Work**
- Convert scanned documents to editable text
- Extract text from images in presentations
- Digitize printed materials

### **For Personal Use**
- Convert photos of notes to digital text
- Extract text from social media screenshots
- Digitize old documents or letters

---

## ⚙️ **Settings & Options**

### **Current Settings** (Tools → TejOCR → Settings)
- **Dependency Status**: Shows what's installed and working
- **Installation Help**: Guides you through fixing missing components
- **Version Information**: Shows what version you have

### **Coming Soon** (Future Updates)
- **Language Selection**: Choose what language to recognize
- **Output Options**: Choose where to put the recognized text
- **Quality Settings**: Adjust for speed vs. accuracy

---

## 🆘 **Getting Help**

### **Built-in Help**
- **Tools → TejOCR → Settings**: First place to check when something's wrong
- **Error Messages**: Usually contain helpful instructions

### **Self-Help Checklist**
1. ✅ Is TejOCR installed? (Check Tools menu)
2. ✅ Are dependencies working? (Check Settings dialog)
3. ✅ Is your image clear and readable?
4. ✅ Did you click where you want the text to appear?
5. ✅ Have you restarted LibreOffice after installation?

### **Still Need Help?**
- Take a screenshot of any error messages
- Note what you were trying to do when the problem occurred
- Check if the same problem happens with different images

---

**Remember: TejOCR is designed to be simple and helpful. Most issues can be solved by checking the Settings dialog and following the guidance there!**

*This documentation is for TejOCR v0.1.4. For technical details, see technical.md* 