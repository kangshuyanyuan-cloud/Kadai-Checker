from winotify import Notification
import os
toast = Notification(app_id='Test', title='Test No Quotes', msg='Test')
toast.add_actions(label='Test Button', launch=os.path.abspath('restore_window.vbs'))
toast.show()
print('SUCCESS')
