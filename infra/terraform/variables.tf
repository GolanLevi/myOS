variable "tenancy_ocid" {
  type = string
}

variable "user_ocid" {
  type = string
}

variable "fingerprint" {
  type = string
}

variable "private_key_path" {
  type = string
}

variable "region" {
  type = string
}

variable "compartment_ocid" {
  type = string
}

variable "ssh_public_key_path" {
  type = string
}

variable "vm_display_name" {
  type    = string
  default = "myos-agents-a1"
}

variable "repo_url" {
  type = string
}

variable "repo_branch" {
  type    = string
  default = "main"
}

variable "deploy_timer" {
  type    = string
  default = "*/5 * * * *"
}

variable "shape" {
  type    = string
  default = "VM.Standard.E2.1.Micro"
}

variable "flex_ocpus" {
  type    = number
  default = null
}

variable "flex_memory_in_gbs" {
  type    = number
  default = null
}

variable "availability_domain_index" {
  type    = number
  default = 0
}

variable "fault_domain" {
  type    = string
  default = null
}

variable "boot_volume_size_in_gbs" {
  type    = number
  default = 47
}

variable "vcn_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "subnet_cidr" {
  type    = string
  default = "10.42.1.0/24"
}

variable "ubuntu_version" {
  type    = string
  default = "24.04"
}

variable "data_volume_size_in_gbs" {
  type    = number
  default = 50
}