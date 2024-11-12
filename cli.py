from modules.chat_handler import ChatHandler
from modules.case import Case
from pathlib import Path
import yaml
from loguru import logger

CONFIG_PATH = Path(__file__).parent / 'configs' / 'global_configs.yaml'
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config_data = yaml.load(f, Loader=yaml.FullLoader)
LLM_PARAMS = config_data.get('LLM', {})
LLM_ENDPOINT = LLM_PARAMS.get('endpoint')
logger.info(f"LLM_PLATFORM : {LLM_ENDPOINT}")
logger.info(f"LLM_PARAMS: {LLM_PARAMS}")


def test_chat_handler():
    ins = ChatHandler(case_id='test_0',
                      llm_config=LLM_PARAMS)
    ins.generate_general_response(auto_send=True)
    ins.generate_task_related_query_response(missing_params=['modality', 'task'], auto_send=True)


def test_flow():
    ins = Case(case_id='test_1',
               llm_configs=LLM_PARAMS)
    while 1:
        user_in = input("Your Response")
        ins(user_in)


if __name__ == "__main__":
    # test_chat_handler()
    test_flow()
