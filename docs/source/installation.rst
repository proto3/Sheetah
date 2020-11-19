Sheetah installation
====================

Assuming you have Python3 and Virtualenv already installed. Start by cloning
Sheetah's repository.

.. prompt:: bash $

    git clone git@github.com:proto3/Sheetah.git
    cd Sheetah

Now create a virtual environment with virtualenv, activate it and install
packages listed in requirements.txt.

.. prompt:: bash $

    virtualenv -p python3 env       # create
    source env/bin/activate         # activate
    pip install -r requirements.txt # initialize

You can now run Sheetah.

.. prompt:: bash $

    cd sheetah
    ./sheetah.py

Once you're done you can deactivate your virtualenv like this.

.. prompt:: bash $

    deactivate
