# משתמשים בפייתון גרסה קלה ומהירה
FROM python:3.11-slim
# מגדירים את תיקיית העבודה בתוך הקונטיינר
WORKDIR /app

# קודם מעתיקים את רשימת הספריות (כדי לנצל את ה-Cache של דוקר)
COPY requirements.txt .

# מתקינים את הספריות
RUN pip install --no-cache-dir -r requirements.txt

# מעתיקים את כל שאר הקוד פנימה
COPY . .

# חושפים את הפורט הפנימי (8000)
EXPOSE 8000

# הפקודה שתרוץ כשהשרת עולה
CMD ["python", "main.py"]
