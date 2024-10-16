from langchain_core.pydantic_v1 import BaseModel, create_model, Field
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from langchain_openai import ChatOpenAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage

from typing import Union

from pathlib import Path
import yaml
import json

from loguru import logger

DEMO_DICT = {
    'PersonalInfo': {'name': {'field_type': 'str', 'options': None, 'mandatory': False},
                     'is_person_corp': {'field_type': 'str', 'options': ['Personal', 'Corporation', 'Unknown']},
                     'email': {'field_type': 'str', 'options': None, 'mandatory': False},
                     'phone': {'field_type': 'str', 'options': None, 'mandatory': True}}}

DEMO_HISTORY = ChatMessageHistory()
DEMO_HISTORY.add_ai_message("Hi. Describe who you are and how would you like me to contact you(Email or phone call.)")
DEMO_HISTORY.add_user_message("Im Anthony, 18516770170. I would like to ask data for my company.")


class KIExtractor:
    def __init__(self, llm_configs=None):
        if not llm_configs:
            llm_config_path = Path(__file__).parent.parent / 'configs' / 'global_configs.yaml'
            with open(llm_config_path, 'r') as f:
                self.__llm_configs = yaml.load(f, Loader=yaml.FullLoader).get('LLM')
        else:
            self.__llm_configs = llm_configs
        assert self.__llm_configs, 'Cannot acquire LLM configs from either config file or input.'

        kie_config_path = Path(__file__).parent.parent / 'configs' / 'models' / 'key_information.yaml'
        with open(kie_config_path, 'r', encoding='utf-8') as f:
            self.all_models_config = yaml.load(f, Loader=yaml.FullLoader)

        self.prompt_base = Path(__file__).parent.parent / 'prompts'/'classification'

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

    def test_gen_model(self, input_dict=None):
        if input_dict is None:
            input_dict = DEMO_DICT

        return self.generate_model('PersonalInfo', input_dict['PersonalInfo'])

    def test_extract(self, ki_model_name='PersonalInfo', chat_input=DEMO_HISTORY):
        key_info, missing_key = self.extract(ki_model_name, chat_input)
        logger.info(key_info)
        logger.info(missing_key)

    def extract(self, key_information_name, chat_input: ChatMessageHistory):
        logger.info(f"[{key_information_name}]     Starts to extract key information from chat_input: \n{chat_input}")
        prompt_template = self.prompt_base / 'kie_extraction_template.txt'
        with open(prompt_template, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        extraction_model_dict = self.all_models_config.get('KIModels', {}).get(key_information_name)
        if not extraction_model_dict:
            logger.error(f"Failed to retrieve extraction_model_dict for ROUTINE: {key_information_name}")
            raise Exception(f"Failed to retrieve extraction_model_dict for ROUTINE: {key_information_name}")

        pydantic_model = self.generate_model(key_information_name, extraction_model_dict)

        key_information_list_str = json.dumps(list(extraction_model_dict.keys()), indent=2, ensure_ascii=False)

        key_information_explanations = '\n'.join(
            [f'{i}: {extraction_model_dict[i].get("description", "字面意思")}' for i in extraction_model_dict])

        llm_ins = self.create_llm_instance()
        parser = PydanticOutputParser(pydantic_object=pydantic_model)
        retry_parser = OutputFixingParser.from_llm(parser=parser, llm=llm_ins)
        format_instruction = parser.get_format_instructions()
        formatted_messages = "\n".join(
            [f"User: {msg.content}" if isinstance(msg, HumanMessage) else f"AI: {msg.content}"
             for msg in chat_input.messages]
        ) if chat_input.messages else "暂时没有记录"
        prompt = prompt_template.format(key_information_list_str=key_information_list_str,
                                        key_information_explanations=key_information_explanations,
                                        format_instruction=format_instruction,
                                        input_content=formatted_messages)

        res_raw = llm_ins.invoke(prompt)
        res_content = res_raw.content
        answer_instance = retry_parser.parse(res_content)

        mandatory_key_information_list = [i for i in extraction_model_dict if extraction_model_dict[i].get("mandatory", False)]

        missing_mandatory_keys = []

        for mandatory_key in mandatory_key_information_list:
            if not getattr(answer_instance, mandatory_key, None):
                missing_mandatory_keys.append(mandatory_key)

        return answer_instance.__dict__, missing_mandatory_keys

    def classify(self, classify_type, prompt_name, chat_input: ChatMessageHistory, **kwargs):
        logger.info(f"[{classify_type}]     Starts to extract key information from chat_input: \n{chat_input}")
        prompt_template = self.prompt_base / f'{prompt_name}.txt'
        with open(prompt_template, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        classification_model_dict = self.all_models_config.get('Classification', {}).get(classify_type)
        if not classification_model_dict:
            logger.error(f"Failed to retrieve classification_model_dict for CLASSIFICATION: {classify_type}")
            raise Exception(f"Failed to retrieve classification_model_dict for CLASSIFICATION: {classify_type}")

        pydantic_model = self.generate_model(classify_type, classification_model_dict)

        llm_ins = self.create_llm_instance()
        parser = PydanticOutputParser(pydantic_object=pydantic_model)
        retry_parser = OutputFixingParser.from_llm(parser=parser, llm=llm_ins)
        format_instruction = parser.get_format_instructions()
        formatted_messages = "\n".join(
            [f"User: {msg.content}" if isinstance(msg, HumanMessage) else f"AI: {msg.content}"
             for msg in chat_input.messages]
        )
        kwargs['format_instruction'] = format_instruction
        kwargs['input_content'] = formatted_messages
        prompt = prompt_template.format(**kwargs)

        res_raw = llm_ins.invoke(prompt)
        res_content = res_raw.content
        answer_instance = retry_parser.parse(res_content)

        mandatory_key_information_list = [i for i in classification_model_dict if
                                          classification_model_dict[i].get("mandatory", False)]

        missing_mandatory_keys = []

        for mandatory_key in mandatory_key_information_list:
            if not getattr(answer_instance, mandatory_key, None):
                missing_mandatory_keys.append(mandatory_key)

        return answer_instance.__dict__, missing_mandatory_keys


if __name__ == "__main__":
    ins = KIExtractor()
    ins.test_extract()
    # model = ins.test_gen_model()
