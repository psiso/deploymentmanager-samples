# Copyright 2017 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Creates a single project with specified service accounts and APIs enabled."""

import copy
from apis import ApiResourceName

def GenerateConfig(context):
  """Generates config."""

  project_id = context.env['name']
  billing_name = 'billing_' + project_id

  resources = [{
      'name': project_id,
      'type': 'cloudresourcemanager.v1.project',
      'properties': {
          'name': project_id,
          'projectId': project_id,
          'parent': {
              'type': 'organization',
              'id': context.properties['organization-id']
          }
      },
      'accessControl': {
          'gcpIamPolicy':
              MergeCallingServiceAccountWithOwnerPermissinsIntoBindings(
                  context.env, context.properties)
      }
  }, {
      'name': billing_name,
      'type': 'deploymentmanager.v2.virtual.projectBillingInfo',
      'metadata': {
          'dependsOn': [project_id]
      },
      'properties': {
          'name': 'projects/' + project_id,
          'billingAccountName': context.properties['billing-account-name']
      }
  }, {
      'name': 'apis',
      'type': 'apis.py',
      'properties': {
          'project': project_id,
          'billing': billing_name,
          'apis': context.properties['apis'],
          'concurrent_api_activation':
              context.properties['concurrent_api_activation']
      }
  }, {
      'name': 'service-accounts',
      'type': 'service-accounts.py',
      'properties': {
          'project': project_id,
          'service-accounts': context.properties['service-accounts']
      }
  }]
  if context.properties.get('bucket-export-settings'):
    bucket_name = None
    action_dependency = [project_id,
                         ApiResourceName(project_id, 'compute.googleapis.com')]
    if context.properties['bucket-export-settings'].get('create-bucket'):
      bucket_name = project_id + '-export-bucket'
      resources.append({
          'name': bucket_name,
          'type': 'gcp-types/storage-v1:buckets',
          'properties': {
              'project': project_id,
              'name': bucket_name
          },
          'metadata': {
              'dependsOn': [project_id,
                            ApiResourceName(
                                project_id, 'storage-component.googleapis.com')]
          }
      })
      action_dependency.append(bucket_name)
    else:
      bucket_name = context.properties['bucket-export-settings']['bucket-name']
    resources.append({
        'name': 'set-export-bucket',
        'action': 'gcp-types/compute-v1:compute.projects.setUsageExportBucket',
        'properties': {
            'project': project_id,
            'bucketName': 'gs://' + bucket_name
        },
        'metadata': {
            'dependsOn': action_dependency
        }
    })

  return {'resources': resources}

def MergeCallingServiceAccountWithOwnerPermissinsIntoBindings(env, properties):
  """ A helper function that merges the acting service account of the project
      creator as an owner of the project being created
  """
  service_account = ('serviceAccount:{0}@cloudservices.gserviceaccount.com'
                     .format(env['project_number']))
  set_creator_sa_as_owner = {
      'role': 'roles/owner',
      'members': [
          service_account,
      ]
  }
  if 'iam-policy' not in properties:
    return {
        'bindings': [
            set_creator_sa_as_owner,
        ]
    }

  bindings = []
  if 'bindings' in properties['iam-policy']:
    bindings = copy.deepcopy(properties['iam-policy']['bindings'])

  merged = False
  for binding in bindings:
    if binding['role'] == 'roles/owner':
      merged = True
      if service_account not in binding['members']:
        binding['members'].append(service_account)
      break

  if not merged:
    bindings.append(set_creator_sa_as_owner)
  return {'bindings': bindings}
