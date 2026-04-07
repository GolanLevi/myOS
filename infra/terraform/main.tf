terraform {
  required_version = ">= 1.5.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 6.0.0"
    }
  }
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = var.ubuntu_version
  shape                    = var.shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

locals {
  ad_name = data.oci_identity_availability_domains.ads.availability_domains[var.availability_domain_index].name

  is_flex_shape = length(regexall("\\.Flex$", var.shape)) > 0

  raw_hostname_label = substr(replace(lower(var.vm_display_name), "/[^a-z0-9]/", ""), 0, 15)
  hostname_label     = length(local.raw_hostname_label) > 0 ? local.raw_hostname_label : "myosvm"

  ssh_public_key = trimspace(file(var.ssh_public_key_path))
  image_id       = data.oci_core_images.ubuntu.images[0].id

  cloud_init = templatefile("${path.module}/templates/cloud-init.yaml.tftpl", {
    repo_url     = var.repo_url
    repo_branch  = var.repo_branch
    deploy_timer = var.deploy_timer
  })
}

resource "oci_core_vcn" "main" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "${var.vm_display_name}-vcn"
  dns_label      = "myosvcn"
}

resource "oci_core_internet_gateway" "igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.vm_display_name}-igw"
  enabled        = true
}

resource "oci_core_route_table" "public_rt" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.vm_display_name}-public-rt"

  route_rules {
    network_entity_id = oci_core_internet_gateway.igw.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
}

resource "oci_core_security_list" "public_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.vm_display_name}-public-sl"

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"

    tcp_options {
      min = 22
      max = 22
    }
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"

    tcp_options {
      min = 80
      max = 80
    }
  }

  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"

    tcp_options {
      min = 443
      max = 443
    }
  }
}

resource "oci_core_subnet" "public_subnet" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.main.id
  cidr_block                 = var.subnet_cidr
  display_name               = "${var.vm_display_name}-public-subnet"
  dns_label                  = "pubsubnet"
  route_table_id             = oci_core_route_table.public_rt.id
  security_list_ids          = [oci_core_security_list.public_sl.id]
  prohibit_public_ip_on_vnic = false
}

resource "oci_core_instance" "vm" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad_name
  display_name        = var.vm_display_name
  shape               = var.shape
  fault_domain        = var.fault_domain

  dynamic "shape_config" {
    for_each = local.is_flex_shape ? [1] : []
    content {
      ocpus         = var.flex_ocpus
      memory_in_gbs = var.flex_memory_in_gbs
    }
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public_subnet.id
    assign_public_ip = true
    hostname_label   = local.hostname_label
    display_name     = "${var.vm_display_name}-vnic"
  }

  source_details {
    source_type             = "image"
    source_id               = local.image_id
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
  }

  metadata = {
    ssh_authorized_keys = local.ssh_public_key
    user_data           = base64encode(local.cloud_init)
  }
}

resource "oci_core_volume" "data" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad_name
  display_name        = "${var.vm_display_name}-data"
  size_in_gbs         = var.data_volume_size_in_gbs
}

resource "oci_core_volume_attachment" "data_attach" {
  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.vm.id
  volume_id       = oci_core_volume.data.id
  device          = "/dev/oracleoci/oraclevdb"
}

data "oci_core_vnic_attachments" "vm_vnics" {
  compartment_id = var.compartment_ocid
  instance_id    = oci_core_instance.vm.id
}

data "oci_core_vnic" "primary_vnic" {
  vnic_id = data.oci_core_vnic_attachments.vm_vnics.vnic_attachments[0].vnic_id
}
