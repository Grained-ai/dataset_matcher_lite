from pathlib import Path
import yaml
from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel, create_model, Field
from langchain_core.chat_history import BaseChatMessageHistory
from typing import Union
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from langchain_core.messages import HumanMessage
from loguru import logger


class ResponseHelper:
    def __init__(self, llm_configs=None):
        if not llm_configs:
            llm_config_path = Path(__file__).parent.parent / 'configs' / 'global_configs.yaml'
            with open(llm_config_path, 'r') as f:
                self.__llm_configs = yaml.load(f, Loader=yaml.FullLoader).get('LLM')
        else:
            self.__llm_configs = llm_configs
        assert self.__llm_configs, 'Cannot acquire LLM configs from either config file or input.'

        response_model_config_path = Path(__file__).parent.parent / 'configs' / 'models' / 'response.yaml'
        with open(response_model_config_path, 'r', encoding='utf-8') as f:
            self.response_model_config = yaml.load(f, Loader=yaml.FullLoader)

        self.prompt_base = Path(__file__).parent.parent / 'prompts'/'responses'

    @property
    def response_types(self):
        return list(self.response_model_config.get('ResponseModels', {}).keys())

    def create_llm_instance(self, model_name=None):
        if not model_name:
            model_name = self.__llm_configs.get('llm_params', {}).get('model_name')
        return ChatOpenAI(temperature=0.95,
                          model=model_name,
                          openai_api_key=self.__llm_configs.get('llm_params', {}).get('api_token'),
                          openai_api_base=self.__llm_configs.get('endpoint'))

    @staticmethod
    def generate_model(model_name: str, fields: dict) -> BaseModel:
        field_definitions = {}
        for field_name, attributes in fields.items():
            field_type = Union[eval(attributes.get('type', "str")), None]  # 默认类型为str
            mandatory = attributes.get('mandatory', False)
            description = attributes.get('description', '字面意思')
            options = attributes.get('options', None)
            field_definitions[field_name] = (field_type, Field(description=description,
                                                               mandatory=mandatory,
                                                               options=options))
        field_definitions['reason'] = (str, Field(description='做出如上选择得原因。Step by step.'))
        return create_model(model_name, **field_definitions)

    def generate_response(self, response_type, chat_history: BaseChatMessageHistory, extra_note=None, **kwargs):
        logger.info(f"Tried to generate {response_type} ResponseText")
        if response_type not in self.response_types:
            raise Exception(f"Failed to generate response_type: {response_type}. Supports: {self.response_types}")
        prompt_path = self.prompt_base / f'{response_type}.txt'

        if not prompt_path.exists():
            logger.warning(f'Failed to find prompt_template for {response_type}. Will use default prompt_template.')
            prompt_path = self.prompt_base / 'GeneralResponse.txt'
        with open(prompt_path, "r", encoding='utf-8') as f:
            prompt_template = f.read()

        response_model_dict = self.response_model_config.get('ResponseModels').get(response_type)
        pydantic_model = self.generate_model(response_type, response_model_dict)

        llm_ins = self.create_llm_instance()
        parser = PydanticOutputParser(pydantic_object=pydantic_model)
        retry_parser = OutputFixingParser.from_llm(parser=parser, llm=llm_ins)
        format_instruction = parser.get_format_instructions()
        formatted_messages = "\n".join(
            [f"User: {msg.content}" if isinstance(msg, HumanMessage) else f"AI: {msg.content}"
             for msg in chat_history.messages]
        ) if chat_history else "暂时没有记录"

        response_description_raw = self.response_model_config.get("ResponseModelDescription", {}).get(response_type, {})
        prompt_format_kwargs = response_description_raw.copy()
        prompt_format_kwargs['format_instruction'] = format_instruction
        prompt_format_kwargs['input_content'] = formatted_messages
        prompt_format_kwargs.update(kwargs)
        prompt = prompt_template.format(**prompt_format_kwargs)

        if extra_note:
            prompt = '\n\n'.join([prompt, f"Note: {extra_note}"])
        # logger.debug(prompt)
        res_raw = llm_ins.invoke(prompt)
        res_content = res_raw.content
        answer_instance = retry_parser.parse(res_content)

        mandatory_key_information_list = [i for i in response_model_dict if
                                          response_model_dict[i].get("mandatory", False)]

        missing_mandatory_keys = []

        for mandatory_key in mandatory_key_information_list:
            if not getattr(answer_instance, mandatory_key, None):
                missing_mandatory_keys.append(mandatory_key)

        return answer_instance.__dict__, missing_mandatory_keys
