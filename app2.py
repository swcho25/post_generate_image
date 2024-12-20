from flask import Flask, request, jsonify, send_from_directory
from PIL import Image, ImageDraw, ImageFont, ImageStat
import openai
import os
import requests
from io import BytesIO

# Flask 서버 초기화
app = Flask(__name__)

# CORS 허용
from flask_cors import CORS
CORS(app)

# API 키 설정
openai.api_key = ''

# 폴더 경로 설정
STATIC_FOLDER = os.path.join(os.getcwd(), 'static')
HTML_FOLDER = os.path.join(STATIC_FOLDER, 'html')
FONTS_FOLDER = os.path.join(os.getcwd(), 'fonts')
FONT_PATH = os.path.join(FONTS_FOLDER, 'NanumBrush.ttf')  # 예시로 기본 폰트를 설정

# 'static' 폴더 생성
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

def translate_text(text, target_language):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Just tell me the value of the translation of '{text}' to {target_language}"}]
    )
    return response.choices[0].message['content'].strip()

def generate_short_message(message):
    """ChatGPT를 사용해 message를 20글자 이내로 요약."""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"{message}. within 20 letters"}]
    )
    return response.choices[0].message['content'].strip()

#def summarize_message(text):    #요약한 문장 반환
#    response = openai.ChatCompletion.create(
#        model="gpt-3.5-turbo",
#        messages=[{"role": "user", "content": f"Summarize the following message briefly: {text}"}]
#    )
#    return response.choices[0].message['content'].strip()

#def extract_keywords(text):
#    response = openai.ChatCompletion.create(
#        model="gpt-3.5-turbo",
#        messages=[{"role": "user", "content": f"Extract important keywords from this message: {text}"}]
#    )
#    return response.choices[0].message['content'].strip()

#def ask_gpt_for_text_position(image_description):
#    response = openai.ChatCompletion.create(
#        model="gpt-3.5-turbo",
#        messages=[{"role": "user", "content": f"Suggest a text position for the following image: '{image_description}'"}]
#    )
#    return response.choices[0].message['content'].strip()

#def get_best_text_and_border_color(image):
#    stat = ImageStat.Stat(image)
#    r, g, b = stat.mean[:3]
#    brightness = (r * 0.299 + g * 0.587 + b * 0.114)
#    return ('black', 'white') if brightness > 128 else ('white', 'black')

#def adjust_font_size(draw, text, font_path, max_width, max_height):
#    font_size = 30
#    font = ImageFont.truetype(font_path, font_size)
#    while True:
#        bbox = draw.textbbox((0, 0), text, font=font)
#        text_width = bbox[2] - bbox[0]
#        text_height = bbox[3] - bbox[1]
#        if text_width <= max_width and text_height <= max_height:
#            break
#        font_size -= 1
#        font = ImageFont.truetype(font_path, font_size)
#    return font

def calculate_text_position(image, position_hint, text, font):
    """GPT가 제안한 위치에 따라 텍스트 좌표를 계산합니다."""
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    if position_hint == 'top left':
        x, y = 10, 10
    elif position_hint == 'top right':
        x, y = image.width - text_width - 10, 10
    elif position_hint == 'bottom right':
        x, y = image.width - text_width - 10, image.height - text_height - 10
    elif position_hint == 'bottom left':
        x, y = 10, image.height - text_height - 10
    else:
        x = (image.width - text_width) / 2
        y = (image.height - text_height) / 2

    x = max(0, min(x, image.width - text_width))
    y = max(0, min(y, image.height - text_height))
    return x, y

@app.route('/generate', methods=['POST'])
def generate_image():
    try:
        # 1. 클라이언트 요청 데이터 추출
        data = request.json
        title = data.get('title', '제목 없음')
        message = data.get('message', '내용 없음')
        instruction = data.get('instruction', '')
        font_name = data.get('font', 'NanumBrush.ttf')
        text_color = data.get('textColor', 'black')
        position = data.get('position', 'center')
        font_size = data.get('fontSize', 30)

        # 2. 폰트 경로 설정
        font_path = os.path.join(FONTS_FOLDER, font_name)

        # 3. tilte, message, instruction 번역
        translated_title = translate_text(title, "English")
        translated_message = translate_text(message, "English")
        translated_instruction = translate_text(instruction, "English")


        #summarized_message = summarize_message(translated_message)
        #final_message = translate_text(summarized_message, "Korean")
        # keywords = extract_keywords(translated_message)
        
        # 4. message에 "within 20 letters" 추가 및 GPT로 요약
        summary_prompt = f"{translated_message} within 20 letters."
        summarized_message = generate_short_message(summary_prompt)
        
        # 5. 요약된 메시지를 한글로 번역
        result_message = translate_text(summarized_message, "Korean")

        # 6. DALLE로 이미지 생성
        prompt = (
            f"Create an image based on the following keywords: {translated_title}. The image should not contain text, numbers, or special symbols."
            f"{translated_instruction}."
        )
        dalle_response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="512x512"
        )

        # 7. 생성된 이미지 다운로드 및 로드
        image_url = dalle_response['data'][0]['url']
        image_response = requests.get(image_url)
        img = Image.open(BytesIO(image_response.content))

        # 8. 폰트 설정
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            print(f"Font {font_name} not found. Using default font.")
            font = ImageFont.load_default()

        # position_hint = ask_gpt_for_text_position(translated_message)

        # 9. 텍스트 위치 계산
        x, y = calculate_text_position(img, position, result_message, font)

        # 10. 이미지에 텍스트 추가
        draw = ImageDraw.Draw(img)
        draw.text((x, y), result_message, font=font, fill=text_color)

        # font = adjust_font_size(draw, result_message, FONT_PATH, img.width - 20, img.height - 20)

        #for offset in [-1, 1]:
        #    draw.text((x + offset, y), result_message, font=font, fill=border_color)
        #    draw.text((x, y + offset), result_message, font=font, fill=border_color)
        #draw.text((x, y), result_message, font=font, fill=text_color)

        # 11. 이미지 저장
        img_path = os.path.join(STATIC_FOLDER, 'result.png')
        img.save(img_path)

        # 12. 결과 반환
        return jsonify({'imageUrl': f'http://localhost:5000/static/result.png'}), 200

    except Exception as e:
        print(f"Error generating image: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_FOLDER, filename)

# HTML 페이지 서빙
@app.route('/')
def serve_index():
    return send_from_directory(HTML_FOLDER, 'index.html')

@app.route('/fonts/<path:filename>')
def serve_fonts(filename):
    return send_from_directory('fonts', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)