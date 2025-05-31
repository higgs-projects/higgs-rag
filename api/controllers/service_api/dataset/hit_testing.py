from controllers.service_api import api
from controllers.service_api.dataset.hit_testing_base import DatasetsHitTestingBase
from controllers.service_api.wraps import DatasetApiResource


class HitTestingApi(DatasetApiResource, DatasetsHitTestingBase):
    def post(self):
        args = self.parse_args()
        self.hit_testing_args_check(args)

        dataset_id_str = str(args.get("knowledge_id"))
        dataset = self.get_and_validate_dataset(dataset_id_str)

        return self.perform_hit_testing(dataset, args)


api.add_resource(HitTestingApi, "/datasets/retrieve")
