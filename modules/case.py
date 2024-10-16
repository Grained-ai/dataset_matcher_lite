import json
import time
from datetime import datetime
from typing import Union, Optional, List
from pathlib import Path
from modules.chat_handler import ChatHandler
from modules.kie_information_extractor import KIExtractor
from modules.singleton import Singleton
from modules.routines import Routines, Routines

from loguru import logger


class Case(Singleton):
    def __init__(self, case_id: Optional[str] = None, llm_configs=None, case_storage_base: Union[None, Path] = None):
        if not hasattr(self, '_initialized'):
            if case_id is None:
                case_id = f'cid_{str(int(time.time() * 1000))}'

            self.case_id = case_id
            self.__case_storage_base = case_storage_base if case_storage_base else Path(
                __file__).parent.parent / 'storage' / 'cases'
            case_dir = self.__case_storage_base / datetime.now().strftime('%Y-%m-%d') / case_id
            logger.debug(case_dir)
            self.__chat_handler = ChatHandler(case_id=case_id,
                                              llm_config=llm_configs,
                                              storage_base=case_dir)
            self.__kie_extractor = KIExtractor(llm_configs=llm_configs)
            self._initialized = True
        self.__chat_handler.start_conversation()
        self.status = self.load_status()
        logger.success(f"Latest case status loaded {self.status}")
        if not self.status:
            self.initialize_case()

    @property
    def todo_routines(self):
        for r_t in self.status[::-1]:
            if 'TODO' in [r_t['routines'][i] for i in r_t['routines'].keys()]:
                return r_t['routines']

    def initialize_case(self):
        logger.info(f'Starts to initialize case: {self.case_id}.')
        self.register_routine([Routines(0)])
        logger.success(f'Case: {self.case_id} initialized.')

    def load_status(self) -> list:
        status_path = self.__case_storage_base / 'status.json'
        if status_path.exists():
            with open(status_path, 'r', encoding='utf-8') as f:
                status = json.load(f)
        else:
            logger.info("Current case is new.")
            status = []
        return status

    def save_status(self):
        status_path = self.__case_storage_base / 'status.json'
        with open(status_path, 'w', encoding='utf-8') as f:
            json.dump(self.status, f, ensure_ascii=False, indent=4)
        logger.success("Current status updated.")

    def register_routine(self, goto_routines: List[Routines]):
        todo_runtimes = {'routines': {i.name: 'TODO' for i in goto_routines}}
        self.status.append(todo_runtimes)
        logger.warning(f"ROUTINES ON SCHEDULE: {json.dumps(todo_runtimes, ensure_ascii=False, indent=2)}")
        return todo_runtimes

    def add_chat(self, message_text):
        self.__chat_handler.add_chat_history('USER', message_text)

    def take_action(self):
        """
        think and update status.
        :return:
        """
        msgs = self.__chat_handler.chat_history
        latest_msg = msgs[-1] if msgs else None
        current_filter = {}
        raw_results = {}
        routines = {}
        not_finished_routines = []
        for routine_name in self.todo_routines:
            if self.todo_routines[routine_name] == 'TODO':
                routine = Routines[routine_name]

                key_info, missing_key, is_finished, goto_routine = routine.think(
                    kie_extractor_ins=self.__kie_extractor,
                    chat_history=self.__chat_handler.chat_history)

                current_filter.update(key_info)
                raw_results[routine_name] = {'key_info': key_info,
                                             'missing_key': missing_key,
                                             'is_finished': is_finished,
                                             'goto_routine_name': goto_routine.name}
                routines[routine_name] = 'DONE'
                if not is_finished:
                    not_finished_routines.append([Routines[routine_name], {"missing_params": missing_key}])

        self.status[-1].update({'filter': current_filter,
                                'msg': latest_msg,
                                'routines': routines,
                                'raw_result_data': raw_results})
        return not_finished_routines


    def display_current_phase(self):
        logger.warning(f"Detailed status: {json.dumps(self.status, indent=4, ensure_ascii=False)}")

    def __call__(self, message_text):
        logger.info(f"Received user message: {message_text}")
        self.add_chat(message_text)
        self.take_action()
        self.display_current_phase()
        self.response_chat()
