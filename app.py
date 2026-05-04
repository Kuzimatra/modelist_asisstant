import os
import json
import hashlib
import secrets
import torch.nn as nn
import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from torchvision import transforms
from PIL import Image
import io
import traceback
from datetime import datetime
from typing import Dict, Set, List
import torch
torch.set_num_threads(1)

print("=" * 60)
print("🚀 ЗАПУСК ПРИЛОЖЕНИЯ")
print("=" * 60)

app = FastAPI(title="ИИ-ассистент для моделистов")

MODEL_PATH = "best_model.pth"
CSV_PATH = "zvezda_cached.csv"
DATA_FOLDER = "data"
GALLERY_FOLDER = "gallery"
AVATARS_FOLDER = "avatars"

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(GALLERY_FOLDER, exist_ok=True)
os.makedirs(AVATARS_FOLDER, exist_ok=True)

HISTORY_IMAGES_FOLDER = os.path.join(GALLERY_FOLDER, "history")
os.makedirs(HISTORY_IMAGES_FOLDER, exist_ok=True)

HISTORY_PATH = os.path.join(DATA_FOLDER, "history.json")
COLLECTION_PATH = os.path.join(DATA_FOLDER, "collection.json")
USERS_PATH = os.path.join(DATA_FOLDER, "users.json")
GALLERY_PATH = os.path.join(DATA_FOLDER, "gallery.json")
LIKES_PATH = os.path.join(DATA_FOLDER, "likes.json")
NOTIFICATIONS_PATH = os.path.join(DATA_FOLDER, "notifications.json")

static_path = os.path.join("templates", "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory="templates/static"), name="static")
    print(f"✅ Статика подключена: {static_path}")

# =====================================================================
# ЗАГРУЗКА CSV
# =====================================================================

df = pd.DataFrame()
if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH, sep=";", encoding="utf-8-sig")
    df = df.fillna("")
    print(f"✅ Загружено наборов: {len(df)}")
else:
    print(f"⚠️ Файл {CSV_PATH} не найден")

# =====================================================================
# КЛАССЫ
# =====================================================================

CLASS_NAMES_RU = [
    'Bf-109', 'Fw-190', 'Ил-2', 'КВ-1', 'M4 Sherman', 'P-51 Mustang',
    'Panther', 'Spitfire', 'Су-25', 'Т-34-85', 'Т-90', 'Tiger I'
]

# =====================================================================
# ЗАГРУЗКА МОДЕЛИ
# =====================================================================

device = torch.device('cpu')
print(f"🖥️ Устройство: {device}")

model = None

try:
    from efficientnet_pytorch import EfficientNet
    print("📦 Загрузка EfficientNet-B4...")
    model = EfficientNet.from_pretrained('efficientnet-b4')
    model._fc = nn.Linear(model._fc.in_features, 12)
    if os.path.exists(MODEL_PATH):
        print(f"📦 Загрузка весов из {MODEL_PATH}...")
        model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
        model = model.to(device)
        model.eval()
        print("✅ Модель успешно загружена!")
    else:
        print(f"❌ Файл модели не найден: {MODEL_PATH}")
except Exception as e:
    print(f"❌ Ошибка загрузки модели: {e}")

transform = transforms.Compose([
    transforms.Resize(362),
    transforms.CenterCrop(342),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# =====================================================================
# ФУНКЦИИ
# =====================================================================

def find_kits_by_model(model_name: str) -> List[Dict]:
    if df.empty:
        return []
    result = df[df["Модель"].str.contains(model_name, case=False, na=False)]
    if result.empty:
        mask = df.apply(lambda row: row.astype(str).str.contains(model_name, case=False, na=False).any(), axis=1)
        result = df[mask]
    records = result.to_dict("records")
    cleaned_records = []
    for record in records:
        cleaned = {}
        for key, value in record.items():
            if pd.isna(value):
                cleaned[key] = ""
            else:
                cleaned[key] = str(value) if value else ""
        cleaned_records.append(cleaned)
    return cleaned_records

def predict_image(image_bytes: bytes):
    if model is None:
        return None, 0, []
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        input_tensor = transform(img).unsqueeze(0).to(device)
        with torch.no_grad():
            outputs = model(input_tensor)
            probs = torch.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probs, 1)
        predicted_class = CLASS_NAMES_RU[predicted.item()]
        confidence_score = float(confidence.item() * 100)
        all_probs = probs.cpu().numpy()[0] * 100
        top3_idx = all_probs.argsort()[-3:][::-1]
        top3 = [(CLASS_NAMES_RU[idx], round(float(all_probs[idx]), 1)) for idx in top3_idx]
        return predicted_class, round(confidence_score, 1), top3
    except Exception as e:
        print(f"❌ Ошибка predict: {e}")
        traceback.print_exc()
        return None, 0, []

# =====================================================================
# УВЕДОМЛЕНИЯ
# =====================================================================

def load_notifications() -> Dict:
    if os.path.exists(NOTIFICATIONS_PATH):
        with open(NOTIFICATIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_notifications(data: Dict):
    with open(NOTIFICATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_notification(username: str, from_user: str, type_: str, image_id: int = None):
    notifications = load_notifications()
    if username not in notifications:
        notifications[username] = []
    notifications[username].insert(0, {
        "from_user": from_user,
        "type": type_,
        "image_id": image_id,
        "timestamp": datetime.now().isoformat(),
        "read": False
    })
    if len(notifications[username]) > 50:
        notifications[username] = notifications[username][:50]
    save_notifications(notifications)

# =====================================================================
# ПОЛЬЗОВАТЕЛИ
# =====================================================================

def load_users() -> Dict:
    if os.path.exists(USERS_PATH):
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users: Dict):
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_session_token() -> str:
    return secrets.token_urlsafe(32)

# =====================================================================
# ХРАНИЛИЩА
# =====================================================================

def load_history(username: str = None):
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            all_history = json.load(f)
            if username:
                return all_history.get(username, [])
            return all_history
    return [] if username else {}

def save_history(history: List, username: str):
    all_history = load_history()
    all_history[username] = history[:50]
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(all_history, f, ensure_ascii=False, indent=2)

def load_collection(username: str = None):
    if os.path.exists(COLLECTION_PATH):
        with open(COLLECTION_PATH, "r", encoding="utf-8") as f:
            all_collection = json.load(f)
            if username:
                return all_collection.get(username, [])
            return all_collection
    return [] if username else {}

def save_collection(collection: List, username: str):
    all_collection = load_collection()
    all_collection[username] = collection
    with open(COLLECTION_PATH, "w", encoding="utf-8") as f:
        json.dump(all_collection, f, ensure_ascii=False, indent=2)

def load_gallery() -> List:
    if os.path.exists(GALLERY_PATH):
        with open(GALLERY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_gallery(gallery: List):
    with open(GALLERY_PATH, "w", encoding="utf-8") as f:
        json.dump(gallery, f, ensure_ascii=False, indent=2)

def load_likes() -> Dict[str, Set[int]]:
    if os.path.exists(LIKES_PATH):
        with open(LIKES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {user: set(image_ids) for user, image_ids in data.items()}
    return {}

def save_likes(likes: Dict[str, Set[int]]):
    data = {user: list(image_ids) for user, image_ids in likes.items()}
    with open(LIKES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_likes: Dict[str, Set[int]] = load_likes()
sessions: Dict[str, str] = {}

def read_html(filename: str) -> str:
    path = os.path.join("templates", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"<h1>Файл {filename} не найден</h1>"

# =====================================================================
# СТРАНИЦЫ
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def root(): return HTMLResponse(content=read_html("index.html"))

@app.get("/history", response_class=HTMLResponse)
async def history_page(): return HTMLResponse(content=read_html("history.html"))

@app.get("/collection", response_class=HTMLResponse)
async def collection_page(): return HTMLResponse(content=read_html("collection.html"))

@app.get("/gallery", response_class=HTMLResponse)
async def gallery_page(): return HTMLResponse(content=read_html("gallery.html"))

@app.get("/about", response_class=HTMLResponse)
async def about_page(): return HTMLResponse(content=read_html("about.html"))

@app.get("/guide", response_class=HTMLResponse)
async def guide_page(): return HTMLResponse(content=read_html("guide.html"))

@app.get("/user/{username}", response_class=HTMLResponse)
async def user_profile_page(username: str):
    users = load_users()
    if username not in users:
        return HTMLResponse(content="<h1 style='color:#fff;text-align:center;padding:50px;'>Пользователь не найден</h1>", status_code=404)
    return HTMLResponse(content=read_html("profile.html"))

# =====================================================================
# API АВТОРИЗАЦИИ
# =====================================================================

@app.post("/api/register")
async def register(username: str = Form(...), password: str = Form(...)):
    users = load_users()
    if username in users: return JSONResponse({"error": "Пользователь уже существует"}, status_code=400)
    if len(password) < 10: return JSONResponse({"error": "Пароль должен быть не менее 10 символов"}, status_code=400)
    if not any(c.isupper() for c in password): return JSONResponse({"error": "Пароль должен содержать хотя бы одну заглавную букву"}, status_code=400)
    if not all(c.isascii() and c.isalnum() for c in password): return JSONResponse({"error": "Пароль должен содержать только латинские буквы и цифры"}, status_code=400)
    users[username] = {"password": hash_password(password), "created_at": datetime.now().isoformat()}
    save_users(users)
    token = create_session_token()
    sessions[token] = username
    return {"success": True, "token": token, "username": username}

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    users = load_users()
    if username not in users or users[username]["password"] != hash_password(password):
        return JSONResponse({"error": "Неверное имя пользователя или пароль"}, status_code=401)
    token = create_session_token()
    sessions[token] = username
    return {"success": True, "token": token, "username": username}

@app.get("/api/check-auth")
async def check_auth(token: str):
    if token in sessions: return {"authenticated": True, "username": sessions[token]}
    return {"authenticated": False}

# =====================================================================
# API УВЕДОМЛЕНИЙ
# =====================================================================

@app.get("/api/notifications")
async def get_notifications(token: str):
    if token not in sessions: return []
    return load_notifications().get(sessions[token], [])

@app.post("/api/notifications/clear")
async def clear_notifications(token: str = Form(...)):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    notifications = load_notifications()
    if username in notifications:
        notifications[username] = []
        save_notifications(notifications)
    return {"success": True}

# =====================================================================
# API АВАТАРОВ
# =====================================================================

@app.post("/api/user/avatar")
async def upload_avatar(token: str = Form(...), file: UploadFile = File(...)):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    if not file.content_type or not file.content_type.startswith("image/"): return JSONResponse({"error": "Файл должен быть изображением"}, status_code=400)
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    avatar_filename = f"{username}.{ext}"
    avatar_path = os.path.join(AVATARS_FOLDER, avatar_filename)
    content = await file.read()
    with open(avatar_path, "wb") as f: f.write(content)
    users = load_users()
    if username in users:
        users[username]["avatar"] = f"/avatars/{avatar_filename}"
        save_users(users)
    return {"success": True, "avatar_url": f"/avatars/{avatar_filename}"}

@app.get("/avatars/{filename}")
async def serve_avatar(filename: str):
    filepath = os.path.join(AVATARS_FOLDER, filename)
    if os.path.exists(filepath): return FileResponse(filepath)
    raise HTTPException(status_code=404, detail="Avatar not found")

@app.delete("/api/user/avatar")
async def delete_avatar(token: str = Form(...)):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    users = load_users()
    if username in users and "avatar" in users[username]:
        avatar_path = users[username]["avatar"].replace("/avatars/", "")
        full_path = os.path.join(AVATARS_FOLDER, avatar_path)
        if os.path.exists(full_path): os.remove(full_path)
        users[username].pop("avatar", None)
        save_users(users)
    return {"success": True}

# =====================================================================
# API ПРОФИЛЕЙ
# =====================================================================

@app.get("/api/user/profile/{username}")
async def get_user_profile(username: str):
    users = load_users()
    if username not in users: return JSONResponse({"error": "Пользователь не найден"}, status_code=404)
    gallery = load_gallery()
    user_works = [work for work in gallery if work.get("username") == username]
    collection = load_collection(username)
    history = load_history(username)
    unique_models = len(set(h.get("model_name", "") for h in history))
    return {
        "username": username,
        "created_at": users[username].get("created_at"),
        "avatar": users[username].get("avatar"),
        "stats": {
            "works_count": len(user_works),
            "collection_count": len(collection),
            "recognitions_count": len(history),
            "unique_models": unique_models,
            "total_likes": sum(work.get("likes", 0) for work in user_works)
        },
        "works": user_works
    }

# =====================================================================
# API КОЛЛЕКЦИИ
# =====================================================================

@app.post("/api/collection/add")
async def add_to_collection(request: Request):
    try:
        data = await request.json()
        token = data.get("token"); kit = data.get("kit")
        if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
        username = sessions[token]
        collection = load_collection(username)
        if any(k.get("Артикул") == kit.get("Артикул") for k in collection): return {"error": "duplicate"}
        collection.append(kit)
        save_collection(collection, username)
        return {"success": True}
    except Exception as e: return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/collection")
async def get_collection(token: str):
    if token not in sessions: return []
    return load_collection(sessions[token])

@app.delete("/api/collection/remove/{index}")
async def remove_from_collection(index: int, token: str):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    collection = load_collection(username)
    if 0 <= index < len(collection): collection.pop(index); save_collection(collection, username)
    return {"success": True}

@app.delete("/api/collection/clear")
async def clear_collection(token: str):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    save_collection([], sessions[token])
    return {"success": True}
@app.post("/api/collection/status")
async def update_collection_status(token: str = Form(...), index: int = Form(...), status: str = Form(...)):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    collection = load_collection(username)
    if 0 <= index < len(collection):
        collection[index]["status"] = status
        save_collection(collection, username)
    return {"success": True}

@app.get("/api/kits/all")
async def get_all_kits():
    """Возвращает все наборы из CSV для библиотеки инструкций"""
    if df.empty: return []
    records = df.to_dict("records")
    cleaned = []
    for r in records:
        c = {}
        for k, v in r.items():
            if pd.isna(v): c[k] = ""
            else: c[k] = str(v) if v else ""
        cleaned.append(c)
    return cleaned

# =====================================================================
# API ИСТОРИИ
# =====================================================================

@app.get("/api/history")
async def get_history(token: str):
    if token not in sessions: return []
    return load_history(sessions[token])

@app.delete("/api/history/clear")
async def clear_history(token: str):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    save_history([], sessions[token])
    return {"success": True}

# =====================================================================
# API ГАЛЕРЕИ
# =====================================================================

@app.post("/api/gallery/add")
async def add_to_gallery(
    token: str = Form(...), title: str = Form(...),
    model_name: str = Form(...), scale: str = Form(...),
    description: str = Form(""), file: UploadFile = File(...)
):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{username}_{timestamp}_{file.filename}"
    filepath = os.path.join(GALLERY_FOLDER, filename)
    content = await file.read()
    with open(filepath, "wb") as f: f.write(content)
    gallery = load_gallery()
    new_id = max([item.get("id", 0) for item in gallery], default=-1) + 1
    gallery.insert(0, {
        "id": new_id, "username": username, "title": title,
        "model_name": model_name, "scale": scale, "description": description,
        "image": f"/gallery/{filename}", "images": [f"/gallery/{filename}"],
        "likes": 0, "comments": [], "created_at": datetime.now().isoformat()
    })
    save_gallery(gallery)
    return {"success": True}

@app.post("/api/gallery/add-multiple")
async def add_to_gallery_multiple(
    token: str = Form(...), title: str = Form(...),
    model_name: str = Form(...), scale: str = Form(...),
    description: str = Form(""), files: List[UploadFile] = File(...)
):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    saved_images = []
    for file in files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_") + str(int(datetime.now().microsecond / 1000))
        filename = f"{username}_{timestamp}_{file.filename}"
        filepath = os.path.join(GALLERY_FOLDER, filename)
        content = await file.read()
        with open(filepath, "wb") as f: f.write(content)
        saved_images.append(f"/gallery/{filename}")
    gallery = load_gallery()
    new_id = max([item.get("id", 0) for item in gallery], default=-1) + 1
    gallery.insert(0, {
        "id": new_id, "username": username, "title": title,
        "model_name": model_name, "scale": scale, "description": description,
        "images": saved_images, "image": saved_images[0],
        "likes": 0, "comments": [], "created_at": datetime.now().isoformat()
    })
    save_gallery(gallery)
    return {"success": True}

@app.get("/api/gallery")
async def get_gallery(sort: str = "newest"):
    gallery = load_gallery()
    if sort == "likes": gallery.sort(key=lambda x: x.get("likes", 0), reverse=True)
    elif sort == "comments": gallery.sort(key=lambda x: len(x.get("comments", [])), reverse=True)
    elif sort == "newest": gallery.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    elif sort == "oldest": gallery.sort(key=lambda x: x.get("created_at", ""))
    return gallery

@app.post("/api/gallery/like/{image_id}")
async def like_image(image_id: int, token: str = Form(...)):
    global user_likes
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    gallery = load_gallery()
    found = False
    for work in gallery:
        if work.get("id") == image_id:
            found = True
            if username not in user_likes: user_likes[username] = set()
            if image_id in user_likes[username]: return {"error": "already_liked"}
            user_likes[username].add(image_id)
            work["likes"] = work.get("likes", 0) + 1
            break
    if not found: return JSONResponse({"error": "Изображение не найдено"}, status_code=404)
    save_likes(user_likes); save_gallery(gallery)
    author = work.get("username")
    if author and author != username: add_notification(author, username, "like", image_id)
    return {"success": True, "likes": work["likes"]}

@app.post("/api/gallery/unlike/{image_id}")
async def unlike_image(image_id: int, token: str = Form(...)):
    global user_likes
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    gallery = load_gallery()
    found = False
    for work in gallery:
        if work.get("id") == image_id:
            found = True
            if username not in user_likes or image_id not in user_likes[username]: return {"error": "not_liked"}
            user_likes[username].remove(image_id)
            work["likes"] = max(0, work.get("likes", 0) - 1)
            break
    if not found: return JSONResponse({"error": "Изображение не найдено"}, status_code=404)
    save_likes(user_likes); save_gallery(gallery)
    return {"success": True, "likes": work["likes"]}

@app.get("/api/gallery/user-likes")
async def get_user_likes(token: str):
    if token not in sessions: return []
    return list(user_likes.get(sessions[token], set()))

@app.post("/api/gallery/comment/{image_id}")
async def comment_image(
    image_id: int, token: str = Form(...),
    comment: str = Form(...), reply_to: str = Form(None)
):
    if token not in sessions: return JSONResponse({"error": "Не авторизован"}, status_code=401)
    username = sessions[token]
    gallery = load_gallery()
    found = False
    for work in gallery:
        if work.get("id") == image_id:
            found = True
            comment_id = str(len(work.get("comments", []))) + "_" + datetime.now().strftime("%Y%m%d%H%M%S%f")
            comment_obj = {
                "id": comment_id,
                "username": username,
                "text": comment,
                "created_at": datetime.now().isoformat()
            }
            if reply_to:
                comment_obj["reply_to"] = reply_to
            work.setdefault("comments", []).append(comment_obj)
            break
    if not found: return JSONResponse({"error": "Изображение не найдено"}, status_code=404)
    save_gallery(gallery)
    author = work.get("username")
    if author and author != username: add_notification(author, username, "comment", image_id)
    if reply_to:
        parent_comment = next((c for c in work.get("comments", []) if c.get("id") == reply_to), None)
        if parent_comment and parent_comment.get("username") != username:
            add_notification(parent_comment["username"], username, "reply", image_id)
    return {"success": True, "comment_id": comment_id}

# =====================================================================
# API РАСПОЗНАВАНИЯ
# =====================================================================

@app.post("/predict")
async def predict(request: Request):
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
            model_name = data.get("model_name"); token = data.get("token")
            if model_name:
                kits = find_kits_by_model(model_name)
                if token and token in sessions:
                    username = sessions[token]
                    history = load_history(username)
                    history.insert(0, {"timestamp": datetime.now().isoformat(), "model_name": model_name, "confidence": 100})
                    if len(history) > 50: history = history[:50]
                    save_history(history, username)
                return {"model_name": model_name, "confidence": 100, "top3": [[model_name, 100]], "kits": kits}
        form = await request.form()
        file = form.get("file"); token = form.get("token")
        if not file: return JSONResponse({"error": "Файл не найден"}, status_code=400)
        contents = await file.read()
        predicted_class, confidence, top3 = predict_image(contents)
        if predicted_class is None: return {"error": "Не удалось распознать изображение"}
        kits = find_kits_by_model(predicted_class)
        if token and token in sessions:
            username = sessions[token]
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            history_image_filename = f"{username}_{timestamp_str}.jpg"
            history_image_path = os.path.join(HISTORY_IMAGES_FOLDER, history_image_filename)
            with open(history_image_path, "wb") as f: f.write(contents)
            history = load_history(username)
            history.insert(0, {"timestamp": datetime.now().isoformat(), "model_name": predicted_class, "confidence": confidence, "image_url": f"/gallery/history/{history_image_filename}"})
            if len(history) > 50: history = history[:50]
            save_history(history, username)
        return {"model_name": predicted_class, "confidence": confidence, "top3": [[cls, prob] for cls, prob in top3], "kits": kits}
    except Exception as e:
        print(f"❌ Ошибка: {e}"); traceback.print_exc()
        return {"error": str(e)}

# =====================================================================
# СТАТИКА
# =====================================================================

@app.get("/gallery/{filename:path}")
async def serve_gallery_image(filename: str):
    filepath = os.path.join(GALLERY_FOLDER, filename)
    if os.path.exists(filepath): return FileResponse(filepath)
    raise HTTPException(status_code=404, detail="Image not found")

# =====================================================================
# ЗАПУСК
# =====================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print("\n" + "=" * 60)
    print("🚀 ИИ-ассистент для моделистов")
    print(f"   http://localhost:{port}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port)