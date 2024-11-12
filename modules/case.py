import json
import time
from datetime import datetime
from typing import Union, Optional, List, Dict
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
            self.case_dir = self.__case_storage_base / datetime.now().strftime('%Y-%m-%d') / case_id
            self.__chat_handler = ChatHandler(case_id=case_id,
                                              llm_config=llm_configs,
                                              storage_base=self.case_dir)
            self.__kie_extractor = KIExtractor(llm_configs=llm_configs)
            self._initialized = True
        self.__chat_handler.start_conversation()
        self.status = self.load_status()
        logger.success(f"Latest case status loaded {self.status}")
        if not self.status:
            self.initialize_case()
            self.main()

    @property
    def todo_pointer(self):
        _status = self.status.copy()
        count = len(_status)
        for d_runtime in self.status[::-1]:
            count -= 1
            # If runtime stack got any TODO task.
            if 'TODO' in [d_routine['status'] for d_routine in d_runtime['routines']]:
                return count

    # @property
    # def todo_routines(self) -> List:
    #     for d_runtime in self.status[::-1]:
    #         if 'TODO' in [d_runtime['routines'][d_routine['status']] for d_routine in d_runtime['routines']]:
    #             return d_runtime['routines']

    def initialize_case(self):
        logger.info(f'Starts to initialize case: {self.case_id}.')
        self.register_routines([Routines(0)])
        logger.success(f'Case: {self.case_id} initialized.')

    def load_status(self) -> List:
        status_path = self.case_dir / 'status.json'
        if status_path.exists():
            with open(status_path, 'r', encoding='utf-8') as f:
                status = json.load(f)
        else:
            logger.info("Current case is new.")
            status = []
        return status

    def save_status(self):
        status_path = self.case_dir / 'status.json'
        with open(status_path, 'w', encoding='utf-8') as f:
            json.dump(self.status, f, ensure_ascii=False, indent=4)
        logger.success("Current status updated.")

    def register_routines(self, goto_routines: List[Routines], params: Union[List[Union[Dict, None]], None] = None):
        todo_runtimes = {'routines': [{'name': routine.name, 'params': param, 'status': 'TODO'}
                                      for routine, param in zip(goto_routines, params)]} if params else {
            'routines': [{'name': routine.name, 'params': None, 'status': 'TODO'}
                         for routine in goto_routines]}
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
        # logger.debug()
        latest_msg = msgs.messages[-1].json() if msgs.messages else None
        current_filter = {}
        raw_results = []
        routines = []
        not_finished_routines = []
        response_texts = []
        for d_routine in self.status[self.todo_pointer]['routines']:
            routine_name = d_routine['name']
            routine_status = d_routine['status']
            routine_params = d_routine['params']
            if routine_status == 'TODO':
                routine = Routines[routine_name]
                # Pre response.
                response_text = routine.response_context(self.__chat_handler, is_finished=False)
                response_texts.append(response_text)
                key_info, missing_key, is_finished, goto_routine = routine.think(
                    kie_extractor_ins=self.__kie_extractor,
                    chat_history=self.__chat_handler.chat_history,
                    param_dict=routine_params)
                logger.debug(f'Prev filter: {json.dumps(current_filter, indent=2, ensure_ascii=False)}')
                if key_info:
                    current_filter.update(key_info)
                    logger.debug(f'Modified filter: {json.dumps(current_filter, indent=2, ensure_ascii=False)}')
                routine_run_result = {'routine': routine_name,
                                      'key_info': key_info,
                                      'missing_key': missing_key,
                                      'is_finished': is_finished,
                                      'goto_routine_name': goto_routine.name}
                # Final response
                if not is_finished:
                    not_finished_routines.append([Routines[routine_name], {"missing_params": missing_key}])
                else:
                    response_text = routine.response_context(self.__chat_handler, is_finished=is_finished)
                    response_texts.append(response_text)
                _cur_d_routine = d_routine.copy()
                _cur_d_routine['status'] = 'DONE' if is_finished else "FAIL"
                routines.append(_cur_d_routine)
                raw_results.append(routine_run_result)
            else:
                logger.warning(f"{routine_name} DONE, SKIPPED. {routine_status}")
                routines.append(d_routine.copy())
                raw_results.append({})

        self.status[-1].update({'filter': current_filter,
                                'msg': latest_msg,
                                'routines': routines,
                                'raw_result_data': raw_results})
        return not_finished_routines, response_texts

    def display_current_phase(self):
        logger.warning(f"Detailed status: {json.dumps(self.status, indent=4, ensure_ascii=False)}")

    def response_chat(self, texts):
        for message_text in texts:
            if message_text:
                self.__chat_handler.reply(message_text)
                self.__chat_handler.add_chat_history('AI', message_text)

    def main(self):
        not_finished_routine_lists, response_texts = self.take_action()

        # GOTO_ROUTINES = PREV_FAILED + FIXED_ROUTINES
        goto_routines = [n_r_list[0] for n_r_list in not_finished_routine_lists] + [Routines.TaskOrientedInfo,
                                                                                    Routines.TaskSummarization]
        params = [n_r_list[1] for n_r_list in not_finished_routine_lists] + [None, None]
        self.register_routines(goto_routines=goto_routines,
                               params=params)
        self.response_chat(response_texts)
        self.display_current_phase()
        self.save_status()

    def __call__(self, message_text):
        logger.info(f"Received user message: {message_text}")
        self.add_chat(message_text)
        self.main()
