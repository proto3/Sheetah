Sheetah installation
====================

Assuming you have Python3 and Pipenv already installed. Start by cloning
Sheetah's repository.

.. prompt:: bash $

    git clone git@github.com:proto3/Sheetah.git
    cd Sheetah

Now create a virtual environment with Pipenv. It will automatically get the
packages listed in Pipfile and Pipfile.lock

.. prompt:: bash $

    pipenv install

You can now use the following commands to activate the environment and run
Sheetah.

.. prompt:: bash $

    pipenv shell
    cd sheetah
    ./sheetah.py

Once you're done you can deactivate your pipenv like this.

.. prompt:: bash $

    exit
