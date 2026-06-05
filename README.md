# fastfind
**fastfind is a lightweight python library that lets you search files or directories extremely fast on Windows/Linux in your code while providing high customizability.**
<br>
### Installation
Use the following command to install fastfind:
```bash
pip install fastfind-files
```
<br>

### Usage
Make sure to first import the library before using it in your code.

```python
import fastfind-files as fastfind
```
<br>

Then you can search for a file/folder by using:

```python
result = fastfind.search(query="hidden_file", search_type="any", max_results=1000, timeout=5.0, roots=["C:\\Users"], all_dirs=True, max_files_per_dir=30, exact_match=True, exclude_folders=["C:\\Program_Files"], exclude_keywords=[".txt"])
```
<br>

| Argument | Datatype | Explanation | Default Value |
| --- | --- | --- | --- |
| query | str | The name of the file/folder you want to search for. **Here you can use Wildcards!** | Required |
| roots | list[str] or None | The root directories to search, if None are provided all drives and folders will be searched. | None |
| exact_match | bool | When set to True, the given query has to exactly match the file/folders name instead of just containing it. | False |
| search_type | str, use: "any", "file" or "dir" | Whether you want to search only for files, folders or both. | any |
| max_results | int | How many results will be returned before stopping. | 1000 |
| timeout | float | The time in s of how long it takes before the library times out and stops searching. | 5.0 |
| all_dirs | bool | If set to True, all files, including system files, will be searched that would otherwise wouldn't be searched due to better performance. | False |
| max_files_per_dir | int or None | Limts how many files can be output from one single directory. | None |
| exclude_folders | list[str] or None | Folders whose content will be excluded in the search. The folder itself can still be found. All subfolders will still be searched.  This is not affected by using all_dirs. | None |
| exclude_keywords | list[str] or None | Excludes results that have these given keywords in them. **Here you can use Wildcards!** | None |

<br>

>[!IMPORTANT]
>When you want to **include all subfolders of a folder** in "exclude_folders" or "roots" use **'/Folder/Path/.'** ! When only using **'/Folder/Path/'** all subfolders will still be searched (exclude_folders) or won't be searched (roots):

| Example | C:/Users | C:/Users/User | C:/Users/User/documents | C:/Users/User/file.txt |
| --- | --- | --- | --- | --- |
| exclude_folders=[r"C:/Users"] | visible | hidden | visible | visible |
| exclude_folders=[r"C:/Users/."] | visible | hidden | hidden | hidden |

<br>

### Wildcards
In the arguments **query** and **exclude_keywords** you can choose to use the wildcards `*` and `?`.
<br>

`*` : Stands for any formation of letters/numbers/symbols of any length. So `query="h*e"` would return *house* and *handsome*.<br>
`?` : Stands for one single character of any kind (letter/number/symbol). So `query = "b?ll"` would return *ball* and *bell*
