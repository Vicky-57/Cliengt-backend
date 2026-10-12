from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="frappe_client_portal",
    version="0.0.1",
    description="Frappe Client Portal App for Accounting Submissions, Helpdesk & CSV Exports",
    author="McKHTech",
    author_email="info@mckhtech.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)
