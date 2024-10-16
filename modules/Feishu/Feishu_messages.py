# encoding=utf-8
import json
import time
from pathlib import Path
import yaml


import lark_oapi as lark
from lark_oapi.api.im.v1 import *


class FeishuMessageHandler:
    def __init__(self, config_yaml_path):
        with open(config_yaml_path, 'r') as f:
            configs = yaml.load(f, Loader=yaml.FullLoader)
        self.__app_id = configs.get('app_id')
        self.__app_secret = configs.get('app_secret')

    def send_message_by_template(self, receive_id, template_id, template_variable: dict, receive_id_type='open_id'):
        content = {'type': 'template', 'data': {'template_id': template_id, 'template_variable': template_variable}}
        # 创建client
        client = lark.Client.builder() \
            .app_id(self.__app_id) \
            .app_secret(self.__app_secret) \
            .log_level(lark.LogLevel.DEBUG) \
            .build()

        # 构造请求对象
        request: CreateMessageRequest = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(CreateMessageRequestBody.builder()
                          .receive_id(receive_id)
                          .msg_type("interactive")
                          .content(json.dumps(content, ensure_ascii=False))
                          .build()) \
            .build()

        # 发起请求
        response: CreateMessageResponse = client.im.v1.message.create(request)

        # 处理失败返回
        if not response.success():
            lark.logger.error(
                f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
            return

        # 处理业务结果
        lark.logger.info(lark.JSON.marshal(response.data, indent=4))

    def send_message(self, receive_id, content, receive_id_type='open_id'):
        pass

    def retrieve_file(self, message_id, file_key, store_path: Path, file_type='file'):
        # 创建client
        client = lark.Client.builder() \
            .app_id(self.__app_id) \
            .app_secret(self.__app_secret) \
            .log_level(lark.LogLevel.DEBUG) \
            .build()

        # 构造请求对象
        request: GetMessageResourceRequest = GetMessageResourceRequest.builder() \
            .message_id(message_id) \
            .file_key(file_key) \
            .type(file_type) \
            .build()

        # 发起请求
        response: GetMessageResourceResponse = client.im.v1.message_resource.get(request)

        # 处理失败返回
        if not response.success():
            lark.logger.error(
                f"client.im.v1.message_resource.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
            return

        # 处理业务结果
        file_name = response.file_name if response.file_name else f"{int(time.time()*1000)}.jpg"
        stored_path = store_path / file_name
        if stored_path.exists():
            return stored_path
        f = open(stored_path, "wb")
        f.write(response.file.read())
        f.close()
        return stored_path


if __name__ == "__main__":
    pass