import json
import requests
from tqdm import tqdm
import os
import subprocess
import tempfile
import re
from jsonpath import jsonpath
from lxml import etree



# 获取当前脚本文件的绝对路径
file_path = os.path.abspath(__file__)
# 获取当前脚本文件所在的父级文件夹路径
parent_directory = os.path.dirname(file_path)
# 将当前工作目录更改为父级文件夹
os.chdir(parent_directory) 

with open(f'./config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
FOLDER_PATH = config['folder_path']
FFMPEG_PATH = config['ffmpeg_path']
COOKIE = config['cookie']
ONLY_AUDIO = config['only_audio']


def standard_file_name(string):
    pattern = r"[^a-zA-Z0-9\u4E00-\u9FA5]+"  # 匹配非汉字数字英文的字符
    return re.sub(pattern, "", string)


class BiliBiliVideo:

    def __init__(self, url):
        self.url = url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
            'Referer': 'https://www.bilibili.com/'
        }
        self.cookie = COOKIE
        self.video_url = None
        self.audio_url = None
        self.title = None

    def analyze(self):
        """为实例自身添加三个属性：视频链接，音频链接，标题"""
        self.headers['Cookie'] = self.cookie
        resp = requests.get(url=self.url, headers=self.headers)
        # with open('index.html', 'w', encoding='utf-8') as f:
        #     f.write(resp.text)
        self.title, json_info = self._extract_json_from_html(resp.text)
        # with open('index.json', 'w', encoding='utf-8') as f:
        #     json.dump(json_info, f, indent=4, ensure_ascii=False)
        self.video_url, self.audio_url = self._extract_urls_from_json(json_info)
        return (self.video_url, self.audio_url, self.title)
        # videos, audios = self._extract_urls_from_json(json_info)
        # self.video_url, self.audio_url = (videos[list(videos.keys())[0]][0], audios[0])
        # return (videos, audios, self.title)

    def download(self, video_url, audio_url, title, folder_path=FOLDER_PATH, only_audio=ONLY_AUDIO):
        """
        在虚拟环境中下载视频和音频文件，用 ffmpeg 合成它们，再保存在指定目录中
        :param folder_path: "D:\\Music\\"
        :param title: "xxx"
        """
        # 只下载音频
        if only_audio:
            path = folder_path + standard_file_name(title) + '.mp3'
            with open(path,  'ab') as f:
                resp = requests.get(url=audio_url, headers=self.headers, stream=True)
                for chunk in tqdm(resp.iter_content(1024), desc='正在下载音频', unit='kb'):
                    f.write(chunk)
            return path

        path = folder_path + standard_file_name(title) + '.mp4'
        # 创建两个临时文件储存音频和视频
        video_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')

        resp = requests.get(url=video_url, headers=self.headers, stream=True)
        for chunk in tqdm(resp.iter_content(1024), desc='正在下载视频', unit='kb'):
            video_temp.write(chunk)
        video_temp.close()  # 关闭文件，完成写入操作

        resp = requests.get(url=audio_url, headers=self.headers, stream=True)
        for chunk in tqdm(resp.iter_content(1024), desc='正在下载音频', unit='kb'):
            audio_temp.write(chunk)
        audio_temp.close()  # 关闭文件，完成写入操作

        # 使用ffmpeg合并音频和视频
        ffmpeg_command = [
            FFMPEG_PATH, '-y', '-i', audio_temp.name, '-i', video_temp.name,
            '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental',
            path
        ]

        # 如果子进程的执行过程中有标准输出，它将被捕获并存储在 subprocess.run()
        subprocess.run(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # 删除临时的音频和视频文件
        os.unlink(video_temp.name)
        os.unlink(audio_temp.name)

        return path


    def _extract_json_from_html(self, html):
        """
        从 html 中提取 playinfo 的 json 信息
        :return: (标题, Json文件)
        """
        root = etree.HTML(html)
        title = root.xpath('//title/text()')[0].replace('_哔哩哔哩_bilibili', '')
        pattern = re.compile(r'<script>window.__playinfo__=(.*?)</script><script>')
        result = pattern.findall(html)[0]
        return (title, json.loads(result))

    def _extract_urls_from_json(self, json_info):
        """从 json 中提取音视频 url"""
        video_url = jsonpath(json_info, f'$..video..baseUrl')[0]
        audio_url = jsonpath(json_info, f'$..audio..baseUrl')[0]
        return video_url, audio_url


def main():
    print(f'保存路径：“{FOLDER_PATH}”')
    if ONLY_AUDIO:
        print('(已设置只下载音频)')
    while True:
        print()
        url = input('链接 >>>')
        bv = BiliBiliVideo(url)
        print(f'\n检索到视频标题 ---> {bv.analyze()[2]}')
        path = bv.download(bv.video_url, bv.audio_url, bv.title)
        print(f'已下载至 “{path}”')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'\n错误：{e}')
        input()
