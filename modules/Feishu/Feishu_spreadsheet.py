import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *
import yaml
import requests


class FeishuSpreadsheetHandler():
    def __init__(self, config_yaml_path, global_token_type=lark.AccessTokenType.TENANT):
        self.__global_token_type = global_token_type
        with open(config_yaml_path, 'r') as f:
            configs = yaml.load(f, Loader=yaml.FullLoader)
        self.__app_id = configs.get('app_id')
        self.__app_secret = configs.get('app_secret')

    def get_tenant_access_token(self):
        """
        :return: {'code': 0, 'expire': xxx, 'msg': 'ok', 'tenant_access_token': 'xxx'}
        """
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
        }
        data = {'app_id': self.__app_id,
                'app_secret': self.__app_secret}
        res = requests.post(url, headers=headers, json=data)
        return res.json().get('tenant_access_token'), res.json()

    def get_table_fields(self, app_token, table_id, **kwargs):
        client = lark.Client.builder() \
            .app_id(self.__app_id) \
            .app_secret(self.__app_secret) \
            .log_level(lark.LogLevel.DEBUG) \
            .build()

        # 构造请求对象
        request: ListAppTableFieldRequest = ListAppTableFieldRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .view_id(kwargs.get('view_id')) \
            .page_size(kwargs.get('page_size', 50)) \
            .build()

        # 发起请求
        option = lark.RequestOption.builder().user_access_token(self.get_tenant_access_token()).build()
        response: ListAppTableFieldResponse = client.bitable.v1.app_table_field.list(request, option)

        # 处理失败返回
        if not response.success():
            lark.logger.error(
                f"client.bitable.v1.app_table_field.list failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
            return []

        # 处理业务结果
        lark.logger.info(lark.JSON.marshal(response.data, indent=4))

        return [i.__dict__ for i in response.data.items]

    def add_records(self, app_token, table_id, records):
        # 创建client
        client = lark.Client.builder() \
            .app_id(self.__app_id) \
            .app_secret(self.__app_secret) \
            .log_level(lark.LogLevel.DEBUG) \
            .build()

        # records_inserted = {'records': [{'fields': i} for i in records]}

        # 构造请求对象
        request: BatchCreateAppTableRecordRequest = BatchCreateAppTableRecordRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .request_body(BatchCreateAppTableRecordRequestBody.builder()
                          .records([AppTableRecord.builder()
                                   .fields(i)
                                   .build()
                                    for i in records])
                          .build()) \
            .build()

        # 发起请求
        response: BatchCreateAppTableRecordResponse = client.bitable.v1.app_table_record.batch_create(request)

        # 处理失败返回
        if not response.success():
            lark.logger.error(
                f"client.bitable.v1.app_table_record.batch_create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
            return

        # 处理业务结果
        lark.logger.info(lark.JSON.marshal(response.data, indent=4))


if __name__ == "__main__":
    ins = FeishuSpreadsheetHandler(
        r'W:\Personal_Project\NeiRelated\projects\shipment_solution\configs\feishu_config.yaml',
        lark.AccessTokenType.TENANT)
    res = ins.get_table_fields(app_token='B7XnbQTtLapDfDsJj27c7ZgQnLd',
                               table_id='tblSsCLLIEXguHpk',
                               view_id='vewFnBR0nY')
    print(res)
