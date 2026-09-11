import io
import os
import random
import string
import time
import wave
import tempfile
import subprocess
import shutil
import asyncio
from datetime import datetime

import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes


# ============================================================
# НАСТРОЙКИ
# ============================================================

# Лучше хранить токен в переменной окружения BOT_TOKEN.
TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН")

COUNTER_FILE = "photo_counter.txt"
VOICE = "ru-RU-DmitryNeural"


# ============================================================
# FFmpeg
# ============================================================

def find_ffmpeg():
    candidates = [
        shutil.which("ffmpeg"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]

    for path in candidates:
        if path and os.path.isfile(path):
            return path

    raise RuntimeError(
        "FFmpeg не найден. Установи его командой: winget install Gyan.FFmpeg "
        "и перезапусти CMD."
    )


def run_ffmpeg(args):
    ffmpeg = find_ffmpeg()
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"] + args
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg завершился с ошибкой:\n" + result.stderr[-3000:]
        )


# ============================================================
# СЧЕТЧИК ФОТО
# ============================================================

def get_next_photo_number():
    try:
        with open(COUNTER_FILE, "r", encoding="utf-8") as file:
            number = int(file.read().strip())
    except (OSError, ValueError):
        number = 0

    number += 1

    with open(COUNTER_FILE, "w", encoding="utf-8") as file:
        file.write(str(number))

    return number


# ============================================================
# ШРИФТ
# ============================================================

def get_font(size):
    fonts = [
        "arial.ttf",
        "Arial.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]

    for path in fonts:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass

    return ImageFont.load_default()


# ============================================================
# ЦВЕТА
# ============================================================

def random_color():
    return (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
    )


def bright_color():
    return (
        random.randint(120, 255),
        random.randint(120, 255),
        random.randint(120, 255),
    )


def dark_color():
    return (
        random.randint(0, 90),
        random.randint(0, 90),
        random.randint(0, 90),
    )


# ============================================================
# ФИГУРЫ
# ============================================================

def add_shapes(image, amount, bright=False):
    draw = ImageDraw.Draw(image)
    width, height = image.size

    for _ in range(amount):
        color = bright_color() if bright else random_color()

        size = random.randint(30, max(40, width // 2))

        x1 = random.randint(-size, width)
        y1 = random.randint(-size, height)

        x2 = x1 + random.randint(30, size * 2)
        y2 = y1 + random.randint(30, size * 2)

        shape = random.choice(["rectangle", "ellipse", "line"])

        if shape == "rectangle":
            draw.rectangle((x1, y1, x2, y2), fill=color)

        elif shape == "ellipse":
            draw.ellipse((x1, y1, x2, y2), fill=color)

        else:
            draw.line(
                (x1, y1, x2, y2),
                fill=color,
                width=random.randint(2, 25),
            )


def add_giant_shapes(image):
    draw = ImageDraw.Draw(image)
    width, height = image.size

    for _ in range(random.randint(1, 5)):
        color = random_color()

        x1 = random.randint(-width, width // 2)
        y1 = random.randint(-height, height // 2)
        x2 = random.randint(width // 2, width * 2)
        y2 = random.randint(height // 2, height * 2)

        if random.choice([True, False]):
            draw.rectangle((x1, y1, x2, y2), fill=color)
        else:
            draw.ellipse((x1, y1, x2, y2), fill=color)


# ============================================================
# ЦИФРЫ
# ============================================================

def add_numbers(image, amount, min_size, max_size):
    width, height = image.size

    for _ in range(amount):
        number_length = random.choice([1, 2, 3, 4, 5, 6, 8, 9])

        number = "".join(
            random.choice(string.digits)
            for _ in range(number_length)
        )

        font = get_font(random.randint(min_size, max_size))

        layer = Image.new(
            "RGBA",
            (
                max(200, len(number) * max_size),
                max_size * 2,
            ),
            (0, 0, 0, 0),
        )

        draw = ImageDraw.Draw(layer)
        color = random_color()

        draw.text(
            (random.randint(0, 20), random.randint(0, 20)),
            number,
            font=font,
            fill=color + (random.randint(140, 255),),
        )

        if random.random() < 0.2:
            draw.text(
                (10, 10),
                number,
                font=font,
                fill=color + (220,),
                stroke_width=random.randint(1, 4),
                stroke_fill=random_color(),
            )

        layer = layer.rotate(
            random.randint(-80, 80),
            expand=True,
        )

        x = random.randint(-layer.width // 2, width)
        y = random.randint(-layer.height // 2, height)

        image.paste(layer, (x, y), layer)


def add_one_number(image):
    width, height = image.size

    number = str(random.randint(0, 999999999))

    font = get_font(
        random.randint(
            int(width * 0.18),
            int(width * 0.35),
        )
    )

    layer = Image.new(
        "RGBA",
        (width * 2, height),
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(layer)

    draw.text(
        (
            random.randint(0, width // 2),
            random.randint(0, height // 3),
        ),
        number,
        font=font,
        fill=random_color() + (random.randint(150, 255),),
    )

    layer = layer.rotate(
        random.randint(-40, 40),
        expand=True,
    )

    image.paste(
        layer,
        (
            random.randint(-width, width // 2),
            random.randint(-height // 2, height // 2),
        ),
        layer,
    )


# ============================================================
# /gaperaphoto
# ============================================================

def generate_photo():
    seed = time.time_ns() ^ random.getrandbits(64)
    random.seed(seed)

    width, height = random.choice([
        (400, 400),
        (500, 500),
        (600, 600),
        (640, 480),
        (480, 640),
        (700, 500),
        (500, 700),
    ])

    mode = random.choice([
        "one_number",
        "few_numbers",
        "many_numbers",
        "very_many_numbers",
        "only_shapes",
        "many_shapes",
        "shapes_numbers",
        "chaos",
        "giant_shapes",
        "almost_empty",
        "numbers_artifacts",
    ])

    background = random.choice([
        random_color(),
        random_color(),
        bright_color(),
        dark_color(),
    ])

    image = Image.new("RGB", (width, height), background)

    if mode == "one_number":
        add_one_number(image)

    elif mode == "few_numbers":
        add_numbers(image, random.randint(2, 8), 25, 70)

    elif mode == "many_numbers":
        add_numbers(image, random.randint(15, 40), 25, 80)

    elif mode == "very_many_numbers":
        add_numbers(image, random.randint(50, 100), 15, 50)

    elif mode == "only_shapes":
        add_shapes(image, random.randint(3, 20))

    elif mode == "many_shapes":
        add_shapes(image, random.randint(25, 70), bright=True)

    elif mode == "shapes_numbers":
        add_shapes(image, random.randint(5, 25))
        add_numbers(image, random.randint(10, 35), 20, 75)

    elif mode == "chaos":
        add_shapes(image, random.randint(20, 60), bright=True)
        add_numbers(image, random.randint(30, 100), 15, 80)

    elif mode == "giant_shapes":
        add_giant_shapes(image)

    elif mode == "almost_empty":
        if random.random() < 0.4:
            add_one_number(image)

    elif mode == "numbers_artifacts":
        add_numbers(image, random.randint(10, 50), 20, 70)

    if random.random() < 0.5:
        draw = ImageDraw.Draw(image)

        for _ in range(random.randint(5, 30)):
            y = random.randint(0, height - 1)

            draw.line(
                (
                    0,
                    y,
                    width,
                    y + random.randint(-10, 10),
                ),
                fill=random_color(),
                width=random.randint(1, 8),
            )

    image = image.filter(
        ImageFilter.GaussianBlur(random.uniform(0, 2.5))
    )

    if random.random() < 0.8:
        factor = random.choice([2, 3, 4, 5, 6, 8])

        small = image.resize(
            (
                max(20, width // factor),
                max(20, height // factor),
            ),
            Image.Resampling.BILINEAR,
        )

        image = small.resize(
            (width, height),
            Image.Resampling.NEAREST,
        )

    image = ImageEnhance.Contrast(image).enhance(
        random.uniform(0.6, 1.5)
    )

    photo_number = get_next_photo_number()
    generation_time = datetime.now().strftime("%H:%M:%S")

    frame_height = 42

    result = Image.new(
        "RGB",
        (width, height + frame_height),
        (15, 15, 15),
    )

    result.paste(image, (0, 0))

    draw = ImageDraw.Draw(result)

    draw.line(
        (0, height, width, height),
        fill=(75, 75, 75),
        width=1,
    )

    font = get_font(max(12, width // 45))

    text = (
        f"Фото №{photo_number} | "
        f"Сгенерировано: {generation_time}"
    )

    draw.text(
        (10, height + 12),
        text,
        font=font,
        fill=(145, 145, 145),
    )

    buffer = io.BytesIO()

    result.save(
        buffer,
        format="JPEG",
        quality=random.randint(8, 55),
    )

    buffer.seek(0)
    return buffer


# ============================================================
# AUDIO: WAV БЕЗ PYDUB
# ============================================================

SAMPLE_RATE = 48000


def write_wav(filename, samples):
    with wave.open(filename, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)

        frames = bytearray()

        for value in samples:
            value = max(-32768, min(32767, int(value)))
            frames.extend(value.to_bytes(2, "little", signed=True))

        wav.writeframes(frames)


def generate_noise_wav(filename, duration_ms, strength):
    count = int(SAMPLE_RATE * duration_ms / 1000)

    samples = (
        random.uniform(-32768, 32767) * strength
        for _ in range(count)
    )

    write_wav(filename, samples)


def generate_beeps_wav(filename):
    pieces = []

    for _ in range(random.randint(2, 15)):
        frequency = random.randint(250, 5000)
        duration_ms = random.randint(40, 700)
        pause_ms = random.randint(30, 600)
        amplitude = random.uniform(0.04, 0.25)

        beep_count = int(SAMPLE_RATE * duration_ms / 1000)
        pause_count = int(SAMPLE_RATE * pause_ms / 1000)

        for i in range(beep_count):
            t = i / SAMPLE_RATE

            # Лёгкое затухание по краям
            edge = min(
                1.0,
                i / max(1, SAMPLE_RATE * 0.01),
                (beep_count - i) / max(1, SAMPLE_RATE * 0.01),
            )

            pieces.append(
                32767
                * amplitude
                * edge
                * __import__("math").sin(2 * __import__("math").pi * frequency * t)
            )

        pieces.extend([0] * pause_count)

    if not pieces:
        pieces = [0] * SAMPLE_RATE

    write_wav(filename, pieces)


# ============================================================
# МУЖСКОЙ ГОЛОС EDGE TTS
# ============================================================

async def generate_voice(text, filename):
    # ВАЖНО: edge-tts требует знак у pitch.
    rate = random.choice([
        "-30%",
        "-35%",
        "-40%",
        "-45%",
        "-50%",
    ])

    pitch = random.choice([
        "-3Hz",
        "-2Hz",
        "+0Hz",
        "+2Hz",
    ])

    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=rate,
        pitch=pitch,
    )

    await communicate.save(filename)


# ============================================================
# АУДИО ОБРАБОТКА
# ============================================================

def convert_to_opus(input_file, output_file, gain_db=0):
    run_ffmpeg([
        "-i", input_file,
        "-af", f"volume={gain_db}dB",
        "-c:a", "libopus",
        "-b:a", "48k",
        "-vbr", "on",
        "-application", "voip",
        output_file,
    ])


def mix_audio_files(files, output_file, volumes=None):
    if not files:
        raise RuntimeError("Нет аудиофайлов для смешивания.")

    if volumes is None:
        volumes = [1.0] * len(files)

    inputs = []
    filters = []

    for i, (filename, volume) in enumerate(zip(files, volumes)):
        inputs += ["-i", filename]
        filters.append(f"[{i}:a]volume={volume}[a{i}]")

    labels = "".join(f"[a{i}]" for i in range(len(files)))

    filter_complex = (
        ";".join(filters)
        + ";"
        + labels
        + f"amix=inputs={len(files)}:duration=longest:"
          f"dropout_transition=0:normalize=0[mix]"
    )

    run_ffmpeg([
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[mix]",
        "-c:a", "libopus",
        "-b:a", "48k",
        "-vbr", "on",
        "-application", "voip",
        output_file,
    ])


def apply_fade_and_gain(input_file, output_file):
    # Получаем длительность через ffmpeg и просто применяем
    # безопасные fade для файлов любой длины.
    gain = random.uniform(-5, 2)

    run_ffmpeg([
        "-i", input_file,
        "-af",
        f"volume={gain}dB,"
        "afade=t=in:d=0.08,"
        "afade=t=out:st=0:d=0.18",
        "-c:a", "libopus",
        "-b:a", "48k",
        "-vbr", "on",
        "-application", "voip",
        output_file,
    ])


# ============================================================
# ФРАЗЫ
# ============================================================

PHRASES = [
    "Система перезапускается",
    "Начинаю перезапуск",
    "Выполняется сброс системы",
    "Производится перезапуск",
    "Запущена процедура сброса",
    "Инициализация перезапуска",
    "Система перезапущена",
    "Перезапуск выполняется",
]


def generate_code():
    length = random.randint(5, 15)

    return "".join(
        random.choice(string.digits)
        for _ in range(length)
    )


# ============================================================
# /gaperareset
# ============================================================

async def gaperareset_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    mode = random.choice([
        "voice",
        "voice_code",
        "beeps",
        "noise",
        "voice_beeps",
        "voice_noise",
        "voice_code_beeps",
        "code_only",
        "noise_beeps",
    ])

    voice_file = None
    noise_file = None
    beeps_file = None
    mixed_file = None
    output_file = None

    try:
        phrase = random.choice(PHRASES)
        code = generate_code()

        voice_file = tempfile.NamedTemporaryFile(
            suffix=".mp3",
            delete=False,
        ).name

        noise_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ).name

        beeps_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ).name

        mixed_file = tempfile.NamedTemporaryFile(
            suffix=".ogg",
            delete=False,
        ).name

        output_file = tempfile.NamedTemporaryFile(
            suffix=".ogg",
            delete=False,
        ).name

        # --------------------------------------------------------
        # ТОЛЬКО ГОЛОС
        # --------------------------------------------------------

        if mode == "voice":
            text = random.choice([
                phrase,
                phrase + ".",
                phrase + ". Ожидайте.",
                phrase + ". Процедура выполняется.",
            ])

            await generate_voice(text, voice_file)
            convert_to_opus(voice_file, mixed_file)

        # --------------------------------------------------------
        # ГОЛОС + КОД
        # --------------------------------------------------------

        elif mode == "voice_code":
            readable_code = " ".join(code)

            text = random.choice([
                f"{phrase}. Код {readable_code}",
                f"Десятичный код {readable_code}",
                f"Код перезапуска {readable_code}",
                f"{phrase}. Десятичный код {readable_code}",
            ])

            await generate_voice(text, voice_file)
            convert_to_opus(voice_file, mixed_file)

        # --------------------------------------------------------
        # ТОЛЬКО ПИСКИ
        # --------------------------------------------------------

        elif mode == "beeps":
            generate_beeps_wav(beeps_file)
            convert_to_opus(beeps_file, mixed_file)

        # --------------------------------------------------------
        # ТОЛЬКО ШУМ
        # --------------------------------------------------------

        elif mode == "noise":
            duration = random.randint(1000, 7000)

            generate_noise_wav(
                noise_file,
                duration,
                random.uniform(0.08, 0.4),
            )

            convert_to_opus(noise_file, mixed_file)

        # --------------------------------------------------------
        # ГОЛОС + ПИСКИ
        # --------------------------------------------------------

        elif mode == "voice_beeps":
            await generate_voice(phrase, voice_file)
            generate_beeps_wav(beeps_file)

            mix_audio_files(
                [voice_file, beeps_file],
                mixed_file,
                [1.0, random.uniform(0.15, 0.45)],
            )

        # --------------------------------------------------------
        # ГОЛОС + ШУМ
        # --------------------------------------------------------

        elif mode == "voice_noise":
            await generate_voice(phrase, voice_file)

            # Делаем шум немного длиннее, чтобы он покрывал голос.
            generate_noise_wav(
                noise_file,
                random.randint(2500, 9000),
                random.uniform(0.03, 0.15),
            )

            mix_audio_files(
                [voice_file, noise_file],
                mixed_file,
                [1.0, 0.5],
            )

        # --------------------------------------------------------
        # ГОЛОС + КОД + ПИСКИ
        # --------------------------------------------------------

        elif mode == "voice_code_beeps":
            readable_code = " ".join(code)

            text = (
                f"{phrase}. "
                f"Код {readable_code}"
            )

            await generate_voice(text, voice_file)
            generate_beeps_wav(beeps_file)

            mix_audio_files(
                [voice_file, beeps_file],
                mixed_file,
                [1.0, random.uniform(0.15, 0.4)],
            )

        # --------------------------------------------------------
        # ТОЛЬКО КОД
        # --------------------------------------------------------

        elif mode == "code_only":
            readable_code = " ".join(code)

            await generate_voice(
                f"Десятичный код {readable_code}",
                voice_file,
            )

            convert_to_opus(voice_file, mixed_file)

        # --------------------------------------------------------
        # ШУМ + ПИСКИ
        # --------------------------------------------------------

        else:
            generate_beeps_wav(beeps_file)

            # Достаточно длинный шум для смешивания.
            generate_noise_wav(
                noise_file,
                random.randint(1500, 8000),
                random.uniform(0.05, 0.25),
            )

            mix_audio_files(
                [noise_file, beeps_file],
                mixed_file,
                [0.6, 1.0],
            )

        # --------------------------------------------------------
        # FADE + СЛУЧАЙНАЯ ГРОМКОСТЬ
        # --------------------------------------------------------

        apply_fade_and_gain(
            mixed_file,
            output_file,
        )

        with open(output_file, "rb") as audio_file:
            await update.message.reply_voice(
                voice=audio_file,
            )

    except Exception as exc:
        # Бот больше не будет молча падать.
        print("Ошибка /gaperareset:", repr(exc))

        try:
            await update.message.reply_text(
                "Ошибка генерации аудио. Проверь установку FFmpeg и edge-tts."
            )
        except Exception:
            pass

    finally:
        for filename in [
            voice_file,
            noise_file,
            beeps_file,
            mixed_file,
            output_file,
        ]:
            if filename:
                try:
                    os.remove(filename)
                except OSError:
                    pass


# ============================================================
# /get
# ============================================================

async def get_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text("Шел нахуй")


# ============================================================
# /timekakoe
# ============================================================

async def timekakoe_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        str(random.randint(0, 1_000_000_000))
    )


# ============================================================
# /gaperaphoto
# ============================================================

async def gaperaphoto_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    photo = generate_photo()

    await update.message.reply_photo(photo=photo)


# ============================================================
# /gaperadox
# ============================================================

def generate_gaperadox():
    letters = string.ascii_letters
    numbers = string.digits

    strange = (
        "𒀀𒀁𒀂𒀃𒀄𒀅𒀆𒀇𒀈𒀉"
        "𒀊𒀋𒀌𒀍𒀎𒀏𒀐𒀑𒀒𒀓"
        "𒀔𒀕𒀖𒀗𒀘𒀙𒀚𒀛𒀜𒀝"
        "𒀞𒀟𒀠𒀡𒀢𒀣𒀤𒀥𒀦𒀧"
        "𒀨𒀩𒀪𒀫𒀬𒀭𒀮𒀯𒀰𒀱"
        "𒀲𒀳𒀴𒀵𒀶𒀷𒀸𒀹𒀺𒀻"
        "𒀼𒀽𒀾𒀿𒁀𒁁𒁂𒁃𒁄𒁅"
        "𒁆𒁇𒁈𒁉𒁊𒁋𒁌𒁍𒁎𒁏"
        "𒁐𒁑𒁒𒁓𒁔𒁕𒁖𒁗𒁘𒁙"
        "𒁚𒁛𒁜𒁝𒁞𒁟𒁠𒁡𒁢𒁣"
        "𒁤𒁥𒁦𒁧𒁨𒁩𒁪𒁫𒁬𒁭"
    )

    length = random.randint(10, 40)

    result = ""

    for _ in range(length):
        group = random.choices(
            [letters, numbers, strange],
            weights=[25, 15, 60],
        )[0]

        result += random.choice(group)

    return result


async def gaperadox_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        generate_gaperadox()
    )


# ============================================================
# МЕНЮ TELEGRAM
# ============================================================

async def post_init(application: Application):
    commands = [
        "get",
        "timekakoe",
        "gaperaphoto",
        "gaperadox",
        "gaperareset",
    ]

    await application.bot.set_my_commands([
        BotCommand(
            command,
            str(random.randint(10000, 999999999)),
        )
        for command in commands
    ])


# ============================================================
# ОШИБКИ TELEGRAM
# ============================================================

async def error_handler(update, context):
    print(
        "Telegram error:",
        repr(context.error),
    )


# ============================================================
# ЗАПУСК
# ============================================================

def main():
    if TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН":
        raise RuntimeError(
            "Не указан токен бота. "
            "Задай переменную BOT_TOKEN или вставь токен в TOKEN."
        )

    # Проверяем FFmpeg ещё до запуска polling.
    ffmpeg = find_ffmpeg()
    print("FFmpeg:", ffmpeg)

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(
        CommandHandler("get", get_command)
    )

    app.add_handler(
        CommandHandler("timekakoe", timekakoe_command)
    )

    app.add_handler(
        CommandHandler("gaperaphoto", gaperaphoto_command)
    )

    app.add_handler(
        CommandHandler("gaperadox", gaperadox_command)
    )

    app.add_handler(
        CommandHandler("gaperareset", gaperareset_command)
    )

    app.add_error_handler(error_handler)

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
