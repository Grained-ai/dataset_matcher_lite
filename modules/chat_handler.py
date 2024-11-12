import datetime
import json
import os
from pathlib import Path
from typing import Union

from langchain_community.chat_message_histories import FileChatMessageHistory
from modules.Feishu.Feishu_messages import FeishuMessageHandler
from modules.response_helper import ResponseHelper

from loguru import logger


class ChatHandler:
    def __init__(self, case_id, llm_config, storage_base: Union[None, Path] = None, reply_proxy_type=None, **kwargs):
        self.__case_id = case_id
        self.__current_step = None
        self.__chat_storage_base = storage_base / 'chats' if storage_base else \
            (Path(__file__).parent.parent / 'storage' / 'cases' / datetime.datetime.now().strftime('%Y-%m-%d')
             / case_id / 'chats')
        os.makedirs(self.__chat_storage_base, exist_ok=True)
        self.start_conversation()
        self.__reply_proxy_type = reply_proxy_type
        if reply_proxy_type == 'Feishu':
            config_yaml_path = kwargs.get('config_yaml_path', None)
            self.message_proxy = FeishuMessageHandler(config_yaml_path=config_yaml_path)
            self.__current_receive_id = kwargs.get('receive_id')
            self.__current_receive_id_type = kwargs.get('receive_id_type')
        else:
            logger.error(f"reply_proxy_type: {reply_proxy_type} not supported. Will use default logger reply mode.")

        self.__response_helper = ResponseHelper(llm_config)

    def generate_greeting(self, auto_send=False):
        response_dict = self.__generate_response('Greeting')
        response_context = response_dict.get("response_context")
        if auto_send:
            self.reply(message_content=response_context)
            self.add_chat_history(role='AI',
                                  content=response_context)
            logger.debug(response_context)
        return response_context

    def generate_general_response(self, auto_send=False):
        response_dict = self.__generate_response('GeneralResponse')
        response_context = response_dict.get("response_context")
        is_finished = response_dict.get("is_finished", False)
        if auto_send:
            self.reply(message_content=response_context)
            self.add_chat_history(role='AI',
                                  content=response_context)
            logger.debug(response_context)
            logger.debug(is_finished)
        return response_context, is_finished

    def generate_task_related_query_response(self, missing_params=None, auto_send=False):
        if not missing_params:
            logger.error("No required queries. Return general reply.")
            response_context = None
        else:
            response_dict = self.__generate_response(response_type='MissingKeyInfo', missing_params=str(missing_params))
            response_context = response_dict.get("response_context")
            if auto_send:
                self.reply(message_content=response_context)
                self.add_chat_history(role='AI',
                                      content=response_context)
                logger.debug(response_context)
        return response_context

    def __generate_response(self, response_type, **kwargs):
        extra_note = None
        response_dict = {}
        for i in range(3):
            response_dict, missing_keys = self.__response_helper.generate_response(response_type=response_type,
                                                                                   chat_history=self.chat_history,
                                                                                   extra_note=extra_note,
                                                                                   **kwargs)
            if missing_keys:
                logger.warning(f"Missing: {missing_keys}. Retry: {i}")
                extra_note = f'{missing_keys} 必须从内容中得到. 目前的提取结果：{json.dumps(response_dict, indent=2, ensure_ascii=False)}'
                continue
            else:
                break
        return response_dict

    def reply(self, message_content, **kwargs):
        if self.__reply_proxy_type == 'Feishu':
            reply_type = kwargs.get("reply_type", 'message')
            if reply_type == 'message':
                self.message_proxy.send_message(receive_id=self.__current_receive_id,
                                                content=message_content,
                                                receive_id_type=self.__current_receive_id_type)
            elif reply_type == 'template':
                template_id = kwargs.get("template_id")
                if not isinstance(message_content, dict):
                    logger.error("message_content should be dict if reply by template.")
                    raise Exception("message_content should be dict if reply by template.")
                self.message_proxy.send_message_by_template(receive_id=self.__current_receive_id,
                                                            template_id=template_id,
                                                            template_variable=message_content)
        else:
            logger.info(f"[REPLY]       {message_content}")

    def load_chat(self, chat_id):
        file_path = self.__chat_storage_base / f"{chat_id}.txt"
        return FileChatMessageHistory(file_path=str(file_path),
                                      encoding='utf-8',
                                      ensure_ascii=False)

    def start_conversation(self):
        chat_id = self.__case_id
        chat_history = self.load_chat(chat_id)
        self.__current_chat_history = chat_history

    def add_chat_history(self, role, content):
        if not self.__current_chat_history:
            logger.error("Not specific step is on. Will store chat to Default")
            self.start_conversation()
        if role == 'AI':
            self.__current_chat_history.add_ai_message(content)
        elif role == 'USER':
            self.__current_chat_history.add_user_message(content)
        logger.success(f"Added {role} chat: {content}")

    @property
    def chat_history(self):
        return self.__current_chat_history
